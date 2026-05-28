"""
简历解析与关键词提取模块

功能:
1. 使用 PyMuPDF (fitz) 解析 PDF 简历，提取纯文本（sort=True 保证多列布局正确）
2. 自动擦除个人隐私信息（手机号、邮箱、身份证号等）
3. 基于关键词集合匹配技术栈标签
4. 关键词频率分析与岗位加权排序
5. 求职岗位识别
6. 候选人姓名智能提取（字号检测 + 启发式正则）
"""

import re
import logging
import fitz  # PyMuPDF
from typing import Tuple, List, Dict, Optional

logger = logging.getLogger(__name__)

# ===== 技术栈关键词库 =====
# 按类别组织，方便后续扩展和维护
TECH_KEYWORDS_MAP = {
    "前端": [
        "JavaScript", "TypeScript", "React", "Vue", "Angular", "Next.js", "Nuxt.js",
        "HTML5", "CSS3", "Sass", "Less", "Tailwind CSS", "Webpack", "Vite",
        "Redux", "Zustand", "Pinia", "React Native", "Flutter", "Electron",
        "jQuery", "Bootstrap", "Ant Design", "Element UI", "shadcn/ui",
        "Axios", "WebSocket", "GraphQL", "REST API", "ECharts", "D3.js",
    ],
    "后端": [
        "Python", "Java", "Golang", "Rust", "C++", "C#", "Node.js", "PHP",
        "FastAPI", "Django", "Flask", "Spring Boot", "Express", "NestJS",
        "Gin", "Actix", ".NET Core", "Laravel",
    ],
    "数据库与缓存": [
        "MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch",
        "SQLite", "Oracle", "SQL Server", "Cassandra", "Neo4j",
        "Memcached", "RabbitMQ", "Kafka",
    ],
    "DevOps与云": [
        "Docker", "Kubernetes", "AWS", "阿里云", "腾讯云", "Azure", "GCP",
        "CI/CD", "Jenkins", "GitHub Actions", "GitLab CI", "Terraform",
        "Nginx", "Linux", "Shell", "Prometheus", "Grafana",
    ],
    "AI与数据": [
        "机器学习", "深度学习", "NLP", "计算机视觉", "PyTorch", "TensorFlow",
        "Pandas", "NumPy", "Scikit-learn", "大模型", "RAG", "LangChain",
        "Prompt Engineering", "Fine-tuning",
    ],
    "通用工具": [
        "Git", "GitHub", "GitLab", "VS Code", "Postman", "Swagger",
        "Jira", "Confluence", "Figma", "微服务", "分布式", "Agile/Scrum",
    ],
}

# 扁平化为单一查找集
ALL_TECH_KEYWORDS: set[str] = set()
for category_keywords in TECH_KEYWORDS_MAP.values():
    ALL_TECH_KEYWORDS.update(category_keywords)

# 大小写不敏感映射表（用户可能写成小写）
_LOWERCASE_MAP: dict[str, str] = {}
for kw in ALL_TECH_KEYWORDS:
    _LOWERCASE_MAP[kw.lower()] = kw


# ===== 隐私信息正则表达式 =====
PRIVACY_PATTERNS = [
    # 中国大陆手机号
    (re.compile(r"1[3-9]\d[\s-]?\d{4}[\s-]?\d{4}"), "[手机号已隐藏]"),
    # 邮箱
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "[邮箱已隐藏]"),
    # 中国大陆身份证号（18位 + 15位）
    (re.compile(
        r"\b[1-9]\d{5}(?:18|19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b"
    ), "[身份证号已隐藏]"),
    (re.compile(r"\b[1-9]\d{7}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}\b"),
     "[身份证号已隐藏]"),
    # QQ 号
    (re.compile(r"[Qq]{2}[：:\s]*\d{5,11}"), "[QQ号已隐藏]"),
    # 微信号
    (re.compile(r"[微Ww]信[号]?[：:\s]*[a-zA-Z0-9_-]{6,20}"), "[微信号已隐藏]"),
    # GitHub 个人主页（保留用户名以便提取技术栈信息，仅脱敏完整 URL）
    (re.compile(r"github\.com/[a-zA-Z0-9_-]+"), ""),  # 保留，这是技术信息
    # 国内家庭住址特征
    (re.compile(
        r"(?:省|市|区|县|街道|镇|村|路|号|单元|栋|楼|层|室)\S{0,20}(?:省|市|区|县|街道|镇|村|路|号|单元|栋|楼|层|室)"
    ), "[地址已隐藏]"),
]


# ===== 姓名提取 =====

_CHINESE_NAME_PATTERN = re.compile(
    r"(?:^|\s|[:：])\s*([一-龥]{2,4})(?:\s|$|[：:，,])"
)

_NOISE_LABELS = {
    "姓名", "名字", "性别", "年龄", "出生", "民族", "政治面貌",
    "电话", "手机", "邮箱", "地址", "学校", "学历", "专业",
    "工作", "经验", "技能", "项目", "教育", "求职", "应聘",
    "目标", "期望", "岗位", "公司", "大学", "学院",
    "男", "女", "本科", "硕士", "博士", "大专",
}


def _extract_name(doc: fitz.Document, first_page_text: str) -> Optional[str]:
    """
    从 PDF 首页智能提取候选人姓名。

    策略优先级：
    1. 字号检测：简历中姓名通常是首页最大字号的中文文本
    2. 启发式正则：在文本开头 200 字内匹配"姓名：XXX"模式
    3. 位置推断：首页左上角的前几个中文字符块
    """
    if doc.page_count == 0:
        return None

    page = doc[0]

    # 策略 1: 字号检测 — 提取最大字号的中文文本块
    try:
        blocks = page.get_text("dict", sort=True)["blocks"]
        spans_by_size: list[tuple[float, str]] = []
        for block in blocks:
            if block.get("type") != 0:
                continue
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text = span.get("text", "").strip()
                    size = span.get("size", 0)
                    if text and re.match(r"^[一-龥]{2,4}$", text):
                        spans_by_size.append((size, text))

        if spans_by_size:
            spans_by_size.sort(key=lambda x: x[0], reverse=True)
            largest_size = spans_by_size[0][0]
            for size, text in spans_by_size:
                if size < largest_size * 0.7:
                    break
                if text not in _NOISE_LABELS and len(text) >= 2:
                    logger.info(f"姓名提取(字号策略): {text} (size={size:.1f})")
                    return text
    except Exception as e:
        logger.debug(f"字号检测异常: {e}")

    # 策略 2: 正则匹配 "姓名：XXX" 模式
    header_text = first_page_text[:300]
    match = re.search(r"(?:姓\s*名|name)[：:\s]*([一-龥]{2,4})", header_text, re.IGNORECASE)
    if match:
        name = match.group(1).strip()
        if name and name not in _NOISE_LABELS:
            logger.info(f"姓名提取(正则策略): {name}")
            return name

    # 策略 3: 首页前 200 字符中提取独立中文姓名
    short_text = first_page_text[:200]
    for m in _CHINESE_NAME_PATTERN.finditer(short_text):
        name = m.group(1).strip()
        if name and name not in _NOISE_LABELS and len(name) >= 2:
            logger.info(f"姓名提取(位置策略): {name}")
            return name

    return None


def _deidentify(text: str) -> str:
    """
    对文本执行数据去标识化（隐私擦除）。

    擦除项：
    - 手机号码
    - 邮箱地址
    - 身份证号码
    - QQ 号
    - 微信号
    - 详细家庭地址
    """
    cleaned = text
    for pattern, replacement in PRIVACY_PATTERNS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned


def _extract_keywords(text: str) -> Tuple[List[str], Dict[str, int]]:
    """
    从文本中提取技术栈关键词，含频率统计。

    策略：
    1. 遍历关键词库，检查是否出现在文本中（大小写不敏感）
    2. 统计每个关键词的出现次数
    3. 对同一技术栈的多种写法做归一化处理
    4. 返回去重后的关键词列表 + 频率统计

    Returns:
        (keywords, frequencies):
        - keywords: 去重后的关键词列表（按出现次数降序）
        - frequencies: {keyword: count} 出现次数统计
    """
    text_lower = text.lower()
    found: dict[str, int] = {}  # {canonical_name: count}

    for key_lower, canonical in _LOWERCASE_MAP.items():
        count = text_lower.count(key_lower)
        if count > 0:
            found[canonical] = found.get(canonical, 0) + count

    # 对特定技术栈做扩展匹配（如 "React" 出现时必定命中）
    # 避免漏掉简历中的简写形式
    extra_checks = {
        "react": "React",
        "vue": "Vue",
        "angular": "Angular",
        "typescript": "TypeScript",
        "javascript": "JavaScript",
        "node": "Node.js",
        "fastapi": "FastAPI",
        "django": "Django",
        "spring": "Spring Boot",
        "mysql": "MySQL",
        "postgresql": "PostgreSQL",
        "mongodb": "MongoDB",
        "redis": "Redis",
        "docker": "Docker",
        "kubernetes": "Kubernetes",
        "aws": "AWS",
        "golang": "Golang",
        "python": "Python",
        "java": "Java",
        "rust": "Rust",
        "linux": "Linux",
        "git": "Git",
        "pytorch": "PyTorch",
        "tensorflow": "TensorFlow",
    }
    for check_lower, canonical in extra_checks.items():
        if check_lower in text_lower:
            if canonical not in found:
                found[canonical] = text_lower.count(check_lower)

    # 按出现频率降序排列
    sorted_kws = sorted(found.keys(), key=lambda k: found[k], reverse=True)

    return sorted_kws, found


def parse_pdf(
    file_bytes: bytes,
) -> Tuple[str, List[str], Dict[str, int], Optional[str], Optional[str]]:
    """
    解析 PDF 简历文件。

    Args:
        file_bytes: PDF 文件的原始字节流

    Returns:
        (cleaned_text, keywords, frequencies, position, candidate_name):
        - cleaned_text: 脱敏后的纯文本内容
        - keywords: 提取到的技术栈关键词列表（按频率降序）
        - frequencies: {keyword: count} 关键词出现次数
        - position: 识别到的求职岗位名称（None 表示未识别）
        - candidate_name: 提取到的候选人姓名（None 表示未识别）

    Raises:
        ValueError: PDF 无法解析或内容为空
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")

    if doc.page_count == 0:
        doc.close()
        raise ValueError("PDF 文件为空，无法解析")

    # 逐页提取文本（sort=True 保证多列布局按阅读顺序提取）
    pages_text: List[str] = []
    for page in doc:
        text = page.get_text("text", sort=True)
        if text.strip():
            pages_text.append(text.strip())

    # 姓名提取需要在 doc 关闭前进行（需要字号信息）
    candidate_name = _extract_name(doc, pages_text[0] if pages_text else "")

    doc.close()

    if not pages_text:
        # 降级策略：尝试 blocks 模式（针对扫描版 PDF）
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            blocks = page.get_text("blocks", sort=True)
            for block in blocks:
                if block[6].strip():
                    pages_text.append(block[6].strip())
        doc.close()

    if not pages_text:
        raise ValueError("PDF 中未检测到可提取的文字内容（可能为图片扫描版，建议手动输入技术标签）")

    full_text = "\n".join(pages_text)

    # 将候选人姓名注入文本头部（确保 AI 面试官始终能看到）
    if candidate_name:
        full_text = f"候选人姓名：{candidate_name}\n\n{full_text}"

    # 隐私脱敏
    cleaned_text = _deidentify(full_text)

    # 关键词提取（含频率）
    keywords, frequencies = _extract_keywords(cleaned_text)

    # 岗位识别
    from app.services.position_analyzer import extract_position_from_text
    position = extract_position_from_text(cleaned_text)

    return cleaned_text, keywords, frequencies, position, candidate_name


def parse_pdf_async(
    file_bytes: bytes,
) -> Tuple[str, List[str], Dict[str, int], Optional[str], Optional[str]]:
    """
    异步友好的简历解析（同步包装）。

    使用方法：
        import asyncio
        cleaned, keywords, freqs, position, name = await asyncio.to_thread(parse_pdf, file_bytes)
    """
    return parse_pdf(file_bytes)