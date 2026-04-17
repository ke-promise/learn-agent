from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.core.container import AppContainer
from app.models.schemas import ChatRequest, ChatResponse


router = APIRouter(prefix='/chat')


@router.post('', response_model=ChatResponse)
async def chat(payload: ChatRequest, container: AppContainer = Depends(get_container)) -> ChatResponse:
    """聊天主入口。

    这里故意不写任何业务判断，所有复杂编排都交给 `Orchestrator`，
    这样接口层可以保持稳定，而业务流程可以在编排层自由演进。
    """
    return await container.orchestrator.run_chat(payload)