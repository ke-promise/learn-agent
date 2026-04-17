from fastapi import APIRouter, Depends

from app.api.deps import get_container
from app.core.container import AppContainer
from app.models.schemas import OverviewResponse


router = APIRouter(prefix='/overview')


@router.get('', response_model=OverviewResponse)
def get_overview(container: AppContainer = Depends(get_container)) -> OverviewResponse:
    """返回前端首页需要的概览统计。"""
    return container.dashboard_service.get_overview()