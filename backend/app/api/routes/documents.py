from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.deps import get_container
from app.core.container import AppContainer
from app.models.schemas import DocumentListResponse, DocumentUploadResponse


router = APIRouter(prefix='/documents')


@router.post('/upload', response_model=DocumentUploadResponse)
async def upload_document(
    title: str = Form(...),
    source: str = Form(...),
    content: str = Form(''),
    file: UploadFile | None = File(default=None),
    container: AppContainer = Depends(get_container),
) -> DocumentUploadResponse:
    """上传并摄取知识文档。

    支持两种输入来源：
    - 直接传文本内容
    - 上传原始文件，由服务层自行解析
    """
    return await container.knowledge_service.ingest_document(title=title, source=source, content=content, file=file)


@router.get('', response_model=DocumentListResponse)
def list_documents(container: AppContainer = Depends(get_container)) -> DocumentListResponse:
    """返回最近导入的知识文档列表。"""
    return container.knowledge_service.list_documents()