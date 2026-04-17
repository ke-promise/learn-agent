from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from time import perf_counter
from typing import Any

from app.models.schemas import TraceStep


@dataclass
class AgentResult:
    """单个 Agent 节点的统一返回结构。"""

    data: dict[str, Any]
    trace: list[TraceStep] = field(default_factory=list)


class BaseAgent:
    """所有 Agent 的公共基类。"""

    name: str = 'agent'

    def trace(self, step_name: str, start_time: float, input_data: dict[str, Any], output_data: dict[str, Any]) -> TraceStep:
        """生成一条 trace 记录。

        这里统一在基类中做，是为了保证不同 Agent 的 trace 格式一致，
        前端才能稳定展示调用链。
        """
        return TraceStep(
            agent_name=self.name,
            step_name=step_name,
            input_data=input_data,
            output_data=output_data,
            duration_ms=int((perf_counter() - start_time) * 1000),
            created_at=datetime.utcnow(),
        )