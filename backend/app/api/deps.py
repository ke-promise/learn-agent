from fastapi import Request

from app.core.container import AppContainer


def get_container(request: Request) -> AppContainer:
    """从 FastAPI 应用状态中取出共享依赖容器。"""
    return request.app.state.container