from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, Field


# 让独立报告服务可以直接复用 backend 里的本地汇报模板。
ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / 'backend'
for candidate in [ROOT_DIR, BACKEND_DIR]:
    if str(candidate) not in sys.path:
        sys.path.insert(0, str(candidate))

from app.services.a2a_client import A2AClient


class ReportRequest(BaseModel):
    """报告生成请求体。"""

    topic: str
    facts: dict[str, Any] = Field(default_factory=dict)


app = FastAPI(title='Report Agent Service', version='1.0.0')


@app.get('/health')
def health() -> dict[str, str]:
    """健康检查。"""
    return {'status': 'ok', 'service': 'report-agent'}


@app.post('/report')
async def generate_report(payload: ReportRequest) -> dict[str, str]:
    """生成一份 Markdown 报告。"""
    content = A2AClient._render_local_report(payload.topic, payload.facts)
    return {'content': content}