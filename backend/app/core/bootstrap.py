from fastapi import FastAPI

from app.core.config import settings
from app.core.container import build_container


def bootstrap_app_state(app: FastAPI) -> None:
    """在 FastAPI 启动阶段初始化共享状态。

    这里集中处理两类事情：
    - 创建本地需要的目录
    - 构建依赖容器并挂到 `app.state` 上

    这样接口层就不需要自己关心依赖初始化细节了。
    """
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.storage_dir.mkdir(parents=True, exist_ok=True)
    app.state.container = build_container()