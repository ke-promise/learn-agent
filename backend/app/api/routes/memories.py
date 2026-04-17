from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.core.container import AppContainer
from app.models.schemas import MemoryCreateRequest, MemoryListResponse, MemoryRecord


router = APIRouter(prefix='/memories')


@router.get('/{user_id}', response_model=MemoryListResponse)
def list_memories(user_id: str, container: AppContainer = Depends(get_container)) -> MemoryListResponse:
    """查看指定用户的长期记忆。"""
    return container.memory_service.list_memories(user_id)


@router.post('', response_model=MemoryRecord)
def create_memory(payload: MemoryCreateRequest, container: AppContainer = Depends(get_container)) -> MemoryRecord:
    """手动写入一条长期记忆。"""
    return container.memory_service.create_memory(payload)