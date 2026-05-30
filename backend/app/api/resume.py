import uuid
import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import get_db
from app.models.models import Resume, User
from app.schemas.schemas import ResumeUploadResponse, ResumeKeywordsRequest
from app.api.auth import get_current_user
from app.services.resume_parser import parse_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/resume", tags=["简历解析"])


def _normalize_optional_text(value: str | None, max_length: int) -> str | None:
    if value is None:
        return None
    normalized = " ".join(value.strip().split())
    if not normalized:
        return None
    return normalized[:max_length]


@router.post("/upload", response_model=ResumeUploadResponse)
async def upload_resume(
    file: UploadFile = File(...),
    job_title: str | None = Form(default=None),
    job_description: str | None = Form(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上传并解析简历（PDF）

    流程：
    1. 校验文件类型与大小
    2. 在 Thread Pool 中异步调用 PyMuPDF 解析（避免阻塞事件循环）
    3. 自动脱敏隐私信息、提取技术栈关键词（含频率统计）
    4. 识别求职岗位，应用岗位-技术栈权重排序
    5. 若解析失败（扫描版 PDF 等），返回空关键词，由前端触发降级流
    """
    # ===== 校验文件类型 =====
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=400, detail="仅支持 PDF 格式的简历文件"
        )

    # ===== 校验文件大小 =====
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(status_code=400, detail="文件大小不能超过 10MB")

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="文件内容为空")

    # ===== 异步解析（CPU 密集型操作放到 Thread Pool） =====
    extracted_keywords: list[str] = []
    raw_text: str = ""
    position_name: str | None = None
    candidate_name: str | None = None
    freq_data: dict = {}
    parse_success = False
    normalized_job_title = _normalize_optional_text(job_title, 120)
    normalized_job_description = _normalize_optional_text(job_description, 8000)

    try:
        raw_text, extracted_keywords, freq_data, position_name, candidate_name = (
            await asyncio.to_thread(parse_pdf, content)
        )
        parse_success = True
        logger.info(
            f"简历解析成功 | 用户={current_user.username} | "
            f"姓名={candidate_name or '未识别'} | "
            f"关键词数量={len(extracted_keywords)} | "
            f"岗位={position_name or '未识别'} | "
            f"Top5={extracted_keywords[:5]}"
        )
    except ValueError as e:
        logger.warning(f"简历解析失败(内容无法识别): {file.filename}, 原因: {e}")
    except Exception as e:
        logger.exception(f"简历解析异常: {file.filename}, 错误: {e}")

    # ===== 岗位加权排序 =====
    if position_name and extracted_keywords:
        from app.services.position_analyzer import analyze_position, apply_tech_weights
        position_data = analyze_position(position_name)
        weighted = apply_tech_weights(extracted_keywords, position_data)

        # 按岗位权重重新排序关键词
        extracted_keywords = [kw for kw, _ in weighted]

        # 核心高权重关键词（权重 >= 1.0）
        core_kws = [kw for kw, w in weighted if w >= 1.0]
        logger.info(
            f"岗位加权完成 | 岗位={position_name} | "
            f"核心关键词={core_kws[:6]} | 总关键词={len(extracted_keywords)}"
        )

    # ===== 持久化到数据库 =====
    resume = Resume(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        parsed_keywords={
            "keywords": extracted_keywords,
            "frequencies": freq_data,
            "position": position_name,
            "candidate_name": candidate_name,
            "job_title": normalized_job_title,
            "job_description": normalized_job_description,
        },
        raw_text=raw_text,
    )
    db.add(resume)
    await db.flush()
    await db.refresh(resume)

    # ===== 构建响应 =====
    if parse_success and extracted_keywords:
        pos_suffix = f"，目标岗位：{position_name}" if position_name else ""
        name_prefix = f"候选人：{candidate_name}，" if candidate_name else ""
        message = f"{name_prefix}简历解析成功，识别到 {len(extracted_keywords)} 个技术栈关键词{pos_suffix}"
    elif parse_success and not extracted_keywords:
        message = "简历已解析，但未识别到技术栈关键词，请手动选择"
    else:
        message = "简历中包含复杂排版，无法自动解析，请手动选择技术栈"

    return ResumeUploadResponse(
        id=resume.id,
        parsed_keywords=extracted_keywords,
        message=message,
        job_title=normalized_job_title,
        job_description=normalized_job_description,
    )


@router.post("/keywords", response_model=ResumeUploadResponse)
async def submit_keywords(
    body: ResumeKeywordsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """手动提交技术关键词（降级流）

    当 PDF 自动解析失败时，用户在前端勾选技术标签后调用此接口。
    """
    if not body.keywords:
        raise HTTPException(status_code=400, detail="关键词列表不能为空")

    normalized_job_title = _normalize_optional_text(body.job_title, 120)
    normalized_job_description = _normalize_optional_text(body.job_description, 8000)

    resume = Resume(
        id=str(uuid.uuid4()),
        user_id=current_user.id,
        parsed_keywords={
            "keywords": body.keywords,
            "job_title": normalized_job_title,
            "job_description": normalized_job_description,
        },
    )
    db.add(resume)
    await db.flush()
    await db.refresh(resume)

    return ResumeUploadResponse(
        id=resume.id,
        parsed_keywords=body.keywords,
        message="关键词提交成功",
        job_title=normalized_job_title,
        job_description=normalized_job_description,
    )


@router.post("/job-context", response_model=ResumeUploadResponse)
async def update_job_context(
    body: ResumeKeywordsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新最新简历的目标岗位要求。

    用户可能在简历解析后继续调整岗位 JD；开始面试前同步一次，确保后端 prompt 使用最新岗位要求。
    """
    if not body.keywords:
        raise HTTPException(status_code=400, detail="关键词列表不能为空")

    normalized_job_title = _normalize_optional_text(body.job_title, 120)
    normalized_job_description = _normalize_optional_text(body.job_description, 8000)

    result = await db.execute(
        select(Resume)
        .where(Resume.user_id == current_user.id)
        .order_by(Resume.created_at.desc())
        .limit(1)
    )
    resume = result.scalar_one_or_none()

    if resume:
        metadata = dict(resume.parsed_keywords) if isinstance(resume.parsed_keywords, dict) else {}
        metadata["keywords"] = body.keywords
        metadata["job_title"] = normalized_job_title
        metadata["job_description"] = normalized_job_description
        resume.parsed_keywords = metadata
        await db.flush()
        await db.refresh(resume)
        resume_id = resume.id
        message = "岗位要求已更新"
    else:
        resume = Resume(
            id=str(uuid.uuid4()),
            user_id=current_user.id,
            parsed_keywords={
                "keywords": body.keywords,
                "job_title": normalized_job_title,
                "job_description": normalized_job_description,
            },
        )
        db.add(resume)
        await db.flush()
        await db.refresh(resume)
        resume_id = resume.id
        message = "岗位要求已保存"

    return ResumeUploadResponse(
        id=resume_id,
        parsed_keywords=body.keywords,
        message=message,
        job_title=normalized_job_title,
        job_description=normalized_job_description,
    )
