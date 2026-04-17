from fastapi import APIRouter

from app.api.routes import chat, documents, memories, overview


# 顶层 API 路由聚合器。
api_router = APIRouter()
api_router.include_router(chat.router, tags=['chat'])
api_router.include_router(documents.router, tags=['documents'])
api_router.include_router(memories.router, tags=['memories'])
api_router.include_router(overview.router, tags=['overview'])