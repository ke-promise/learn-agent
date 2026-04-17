from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# `BASE_DIR` 统一指向 backend 目录，后面的数据目录、默认配置都从这里展开。
BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """应用配置对象。

    这里使用 `pydantic-settings` 的原因是：
    - 能直接从环境变量读取配置
    - 保留类型约束，减少字符串配置带来的隐性错误
    - 让本地模式和 Docker 模式共用一套配置入口
    """

    # 统一从 `.env` 读取；即使存在多余字段，也忽略而不是直接报错。
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    # 应用基础信息。
    app_name: str = 'Incident Review Copilot'
    environment: str = 'development'

    # 本地数据目录。JSON 回退模式、上传文件回退模式都会用到这里。
    data_dir: Path = BASE_DIR / 'data'
    storage_dir: Path | None = None

    # 允许按环境切换不同基础设施后端。
    storage_backend: Literal['json', 'postgres'] = 'json'
    conversation_backend: Literal['json', 'redis'] = 'json'
    object_storage_backend: Literal['local', 'minio'] = 'local'

    # 当前项目使用轻量哈希 embedding，因此只需要约定一个固定维度。
    embedding_dimensions: int = 256

    # PostgreSQL / Redis 连接信息。
    postgres_url: str = 'postgresql+psycopg://mini_agent:mini_agent@localhost:5432/mini_agent'
    redis_url: str = 'redis://localhost:6379/0'
    redis_conversation_ttl_seconds: int = 86400

    # MinIO 对象存储配置。
    minio_endpoint: str = 'localhost:9000'
    minio_access_key: str = 'minioadmin'
    minio_secret_key: str = 'minioadmin'
    minio_bucket: str = 'knowledge-files'
    minio_secure: bool = False

    # 外部服务地址：MCP Server、远程报告服务、SQL Agent 服务。
    mcp_server_url: str = ''
    remote_report_agent_url: str = ''
    sql_agent_url: str = ''

    # OCR 相关开关。扫描 PDF 或图片无法直接提文本时会走这里。
    ocr_enabled: bool = True
    ocr_max_pdf_pages: int = 8

    @model_validator(mode='after')
    def populate_paths(self) -> 'Settings':
        """在配置完成后补齐派生路径。

        这样做的好处是：
        - 用户可以只配置 `data_dir`
        - 代码内部仍然可以稳定拿到 `storage_dir`
        """
        if self.storage_dir is None:
            self.storage_dir = self.data_dir / 'storage'
        return self


# 全局单例配置对象。应用启动后，大多数模块都直接依赖它。
settings = Settings()