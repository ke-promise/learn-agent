from __future__ import annotations

from time import perf_counter

from app.agents.base import AgentResult, BaseAgent
from app.models.schemas import IntentType


# 这里额外保留一个中文标签映射，方便前端直接展示更像产品语言的结果。
INTENT_LABELS: dict[IntentType, str] = {
    'knowledge_query': '知识查询',
    'status_analysis': '状态分析',
    'report_generation': '汇报生成',
    'preference_management': '偏好管理',
}


class RouterAgent(BaseAgent):
    """意图分类节点。"""

    name = 'router'

    def route(self, message: str) -> AgentResult:
        """根据关键词做轻量意图判定。"""
        start = perf_counter()
        intent_type: IntentType = 'knowledge_query'
        normalized = message.strip()

        if any(keyword in normalized for keyword in ['汇报', '简报', '复盘总结', '老板', '周报', '报告']):
            intent_type = 'report_generation'
        elif any(keyword in normalized for keyword in ['故障', '指标', '趋势', '风险', '状态', '工单', '分析', '排查']):
            intent_type = 'status_analysis'
        elif any(keyword in normalized for keyword in ['记住', '偏好', '喜欢', '负责', '以后默认', 'memory']):
            intent_type = 'preference_management'

        payload = {
            'intent_type': intent_type,
            'intent_label': INTENT_LABELS[intent_type],
        }
        return AgentResult(data=payload, trace=[self.trace('intent_classification', start, {'message': message}, payload)])