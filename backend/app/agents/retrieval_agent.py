from __future__ import annotations

from time import perf_counter

from app.agents.base import AgentResult, BaseAgent
from app.services.knowledge_service import KnowledgeService


class RetrievalAgent(BaseAgent):
    """知识检索节点。"""

    name = 'retrieval'

    def __init__(self, knowledge_service: KnowledgeService) -> None:
        self.knowledge_service = knowledge_service

    def run(self, query: str) -> AgentResult:
        start = perf_counter()
        citations = [item.model_dump(mode='json') for item in self.knowledge_service.search(query)]
        return AgentResult(
            data={'citations': citations},
            trace=[self.trace('knowledge_retrieval', start, {'query': query}, {'citation_count': len(citations)})],
        )