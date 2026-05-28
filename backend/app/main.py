import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from app.config import settings
from app.api import auth, resume, interview, report, admin, admin_config, admin_dashboard, admin_documents, admin_prompt, admin_audit

# 全局日志配置：确保 INFO 级别日志在所有模块中可见
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时：初始化 Redis 连接池、并发控制、数据库建表
    from app.core.redis import init_redis, close_redis
    from app.core.concurrency import init_slot_manager, shutdown_slot_manager
    from app.models.database import engine, Base

    # 1. Redis
    await init_redis()

    # 2. 并发槽位管理器
    await init_slot_manager()

    # 3. LLM 客户端预检（三模型）
    from app.services.llm_client import get_available_providers
    providers = get_available_providers()
    if providers:
        logger.info(f"LLM 提供商就绪: {', '.join(providers)} | Failover 策略: {' → '.join(providers)}")
        if "deepseek" in providers:
            logger.info(f"  DeepSeek (P1): {settings.DEEPSEEK_BASE_URL} (model=deepseek-chat)")
        if "mimo" in providers:
            logger.info(f"  MiMo (P2): {settings.MIMO_BASE_URL} (model={settings.MIMO_MODEL_NAME})")
        if "qwen" in providers:
            logger.info(f"  Qwen (P3): {settings.QWEN_BASE_URL} (model={settings.QWEN_MODEL_NAME})")
    else:
        logger.warning("未配置任何 LLM API Key，AI 功能将降级为 Mock 模式")

    # 3.5 bcrypt 版本预检（passlib 1.7.4 不兼容 bcrypt>=4.1）
    try:
        import bcrypt
        bcrypt_version = bcrypt.__version__
        if bcrypt_version.startswith("4."):
            logger.info(f"bcrypt 版本检查通过: {bcrypt_version}")
        else:
            logger.critical(
                f"bcrypt 版本不兼容: {bcrypt_version}，需要 4.0.x！"
                f"请执行: pip install bcrypt==4.0.1"
            )
    except Exception as e:
        logger.warning(f"bcrypt 版本检查失败: {e}")

    # 4. 数据库建表
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("数据库表检查/创建完成")
    except Exception as e:
        logger.error(f"数据库表创建失败（应用可能无法正常使用）: {e}")

    # 5. 初始化内置提示词模板
    try:
        from app.services.prompt_service import init_builtin_templates
        await init_builtin_templates()
    except Exception as e:
        logger.warning(f"内置提示词模板初始化失败: {e}")

    logger.info("AceInterviewer 后端启动完成")

    yield

    # 关闭时：清理资源
    await shutdown_slot_manager()
    await close_redis()
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    description="沉浸式 AI 模拟面试平台 API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 配置（开发环境允许前端跨域）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis 滑动窗口限流中间件
from app.core.rate_limit import RateLimitMiddleware
app.add_middleware(RateLimitMiddleware)

# 注册路由
app.include_router(auth.router)
app.include_router(resume.router)
app.include_router(interview.router)
app.include_router(report.router)
app.include_router(admin.router)
app.include_router(admin_config.router)
app.include_router(admin_dashboard.router)
app.include_router(admin_documents.router)
app.include_router(admin_prompt.router)
app.include_router(admin_audit.router)


@app.get("/health")
async def health_check():
    """健康检查接口"""
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.APP_ENV}


@app.get("/health/db")
async def health_check_db():
    """数据库连通性检查"""
    from app.models.database import engine
    try:
        async with engine.connect() as conn:
            await conn.exec_driver_sql("SELECT 1")
        return {"status": "ok", "database": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "error", "database": "disconnected", "detail": str(e)},
        )