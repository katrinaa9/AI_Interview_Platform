import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 应用配置
    APP_ENV: str = "development"
    DEBUG: bool = True
    APP_NAME: str = "AceInterviewer"

    # 数据库
    MYSQL_HOST: str = "localhost"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "aceinterviewer"
    MYSQL_PASSWORD: str = "aceinterviewer123"
    MYSQL_DATABASE: str = "aceinterviewer"

    # Redis
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    # JWT
    JWT_SECRET: str = "dev-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 24  # 24 小时

    # DeepSeek API (主模型)
    DEEPSEEK_API_KEY: str = ""
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"

    # 通义千问 Qwen (备用模型 - DashScope OpenAI 兼容接口)
    QWEN_API_KEY: str = ""
    QWEN_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    QWEN_MODEL_NAME: str = "qwen-plus"

    @property
    def DATABASE_URL(self) -> str:
        return (
            f"mysql+asyncmy://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
        )

    @property
    def DATABASE_URL_SYNC(self) -> str:
        return (
            f"mysql+pymysql://{self.MYSQL_USER}:{self.MYSQL_PASSWORD}"
            f"@{self.MYSQL_HOST}:{self.MYSQL_PORT}/{self.MYSQL_DATABASE}"
        )

    model_config = {
        "env_file": (".env", "../.env"),  # 优先当前目录，其次父目录
        "env_file_encoding": "utf-8",
    }


settings = Settings()