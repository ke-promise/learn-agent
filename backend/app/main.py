from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.bootstrap import bootstrap_app_state
from app.core.config import settings


# 整个后端应用实例。
app = FastAPI(title=settings.app_name, version='1.0.0')

# 项目默认面向本地开发与演示，因此这里直接放开跨域，方便前端独立调试。
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.on_event('startup')
def on_startup() -> None:
    """应用启动时初始化目录、容器和共享依赖。"""
    bootstrap_app_state(app)


@app.get('/health')
def health() -> dict[str, object]:
    """健康检查接口。

    除了返回 `ok`，还顺手暴露当前启用的关键后端，方便联调时判断：
    - 是否走 PostgreSQL / Redis / MinIO
    - 是否接入了 MCP / SQL Agent / Report Agent
    """
    return {
        'status': 'ok',
        'app_name': settings.app_name,
        'environment': settings.environment,
        'storage_backend': settings.storage_backend,
        'conversation_backend': settings.conversation_backend,
        'object_storage_backend': settings.object_storage_backend,
        'mcp_server_enabled': bool(settings.mcp_server_url),
        'report_agent_enabled': bool(settings.remote_report_agent_url),
        'sql_agent_enabled': bool(settings.sql_agent_url),
    }


# 所有业务接口统一挂在 `/api/v1`，便于后续继续迭代版本。
app.include_router(api_router, prefix='/api/v1')