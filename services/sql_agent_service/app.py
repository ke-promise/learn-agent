from __future__ import annotations

import functools
import sys
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel


# 让独立 SQL 服务在单独启动时也能找到 backend 包。
ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / 'backend'
for candidate in [ROOT_DIR, BACKEND_DIR]:
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from app.core.config import settings
from app.core.container import build_container


class SQLAnalysisRequest(BaseModel):
    """自然语言分析请求。"""

    question: str


class SQLExecuteRequest(BaseModel):
    """只读 SQL 执行请求。"""

    sql: str


@functools.lru_cache(maxsize=1)
def _container():
    return build_container()


app = FastAPI(title='SQL Agent Service', version='1.0.0')


@app.get('/health')
def health() -> dict[str, object]:
    """健康检查。"""
    return {
        'status': 'ok',
        'service': 'sql-agent',
        'storage_backend': settings.storage_backend,
    }


@app.post('/analyze')
def analyze(payload: SQLAnalysisRequest) -> dict:
    """把自然语言问题转成 SQL 分析结果。"""
    return _container().ops_service.analyze_question(payload.question)


@app.post('/execute')
def execute(payload: SQLExecuteRequest) -> dict[str, object]:
    """执行只读 SQL。"""
    return {'rows': _container().ops_service.execute_readonly_sql(payload.sql)}