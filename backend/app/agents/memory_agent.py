from __future__ import annotations

from time import perf_counter

from app.agents.base import AgentResult, BaseAgent
from app.services.memory_service import MemoryService


class MemoryAgent(BaseAgent):
    """长期记忆检索节点。"""

    name = 'memory'

    def __init__(self, memory_service: MemoryService) -> None:
        self.memory_service = memory_service

    def run(self, user_id: str, query: str) -> AgentResult:
        start = perf_counter()
        hits = [item.model_dump(mode='json') for item in self.memory_service.search_memories(user_id, query)]
        return AgentResult(
            data={'memory_hits': hits},
            trace=[self.trace('memory_lookup', start, {'user_id': user_id, 'query': query}, {'memory_hit_count': len(hits)})],
        )