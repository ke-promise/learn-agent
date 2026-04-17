from __future__ import annotations

from time import perf_counter

from app.agents.base import AgentResult, BaseAgent
from app.models.schemas import IntentType


class PlannerAgent(BaseAgent):
    """任务规划节点。"""

    name = 'planner'

    def plan(self, intent_type: IntentType) -> AgentResult:
        """把用户意图映射成执行步骤。

        这里的设计思想是：
        - 不让每个请求都跑完整条链
        - 根据任务类型只开启必要节点
        """
        start = perf_counter()
        mapping = {
            'knowledge_query': ['memory', 'retrieval'],
            'status_analysis': ['memory', 'retrieval', 'tool'],
            'report_generation': ['memory', 'retrieval', 'tool', 'report'],
            'preference_management': ['memory'],
        }
        payload = {'plan': mapping[intent_type]}
        return AgentResult(data=payload, trace=[self.trace('task_planning', start, {'intent_type': intent_type}, payload)])