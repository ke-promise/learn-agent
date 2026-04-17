from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any


# 当没有真实数据库时，用这组演示数据支撑工单、指标和 SQL 分析。
FALLBACK_TICKETS = [
    {
        'ticket_id': 'INC-1024',
        'system_name': 'payment',
        'status': 'open',
        'owner': 'platform-team',
        'severity': 'high',
        'summary': 'Payment callback timeout in production',
        'created_at': (datetime.now(UTC) - timedelta(days=1)).isoformat(),
    },
    {
        'ticket_id': 'INC-1025',
        'system_name': 'payment',
        'status': 'closed',
        'owner': 'payment-team',
        'severity': 'medium',
        'summary': 'Retry storm caused callback latency spike',
        'created_at': (datetime.now(UTC) - timedelta(days=3)).isoformat(),
    },
    {
        'ticket_id': 'INC-1026',
        'system_name': 'order',
        'status': 'open',
        'owner': 'order-team',
        'severity': 'medium',
        'summary': 'Order service rate-limit drift',
        'created_at': (datetime.now(UTC) - timedelta(days=2)).isoformat(),
    },
]

FALLBACK_EVENTS = [
    {
        'system_name': 'payment',
        'severity': 'high',
        'status': 'mitigated',
        'ticket_id': 'INC-1024',
        'root_cause': 'Connection pool too small combined with retry storm',
        'duration_minutes': 47,
        'occurred_at': (datetime.now(UTC) - timedelta(days=1)).isoformat(),
    },
    {
        'system_name': 'payment',
        'severity': 'medium',
        'status': 'resolved',
        'ticket_id': 'INC-1025',
        'root_cause': 'Callback worker saturation under peak traffic',
        'duration_minutes': 33,
        'occurred_at': (datetime.now(UTC) - timedelta(days=3)).isoformat(),
    },
    {
        'system_name': 'order',
        'severity': 'medium',
        'status': 'open',
        'ticket_id': 'INC-1026',
        'root_cause': 'Rate-limit threshold drift',
        'duration_minutes': 18,
        'occurred_at': (datetime.now(UTC) - timedelta(days=2)).isoformat(),
    },
]


class OpsService:
    """提供工单、指标与只读 SQL 分析能力。"""

    def __init__(self, store: Any) -> None:
        self.store = store

    def query_metric(self, metric_name: str) -> dict[str, Any]:
        """查询指标。

        有数据库时走真实数据；没有数据库时走内置演示数据。
        """
        if hasattr(self.store, 'query_metric'):
            return self.store.query_metric(metric_name)
        if metric_name == 'incident_count':
            value = len(FALLBACK_EVENTS)
        elif metric_name == 'ticket_backlog':
            value = sum(1 for item in FALLBACK_TICKETS if item['status'] in {'open', 'investigating'})
        elif metric_name == 'alpha_risk_score':
            value = min(100, sum(1 for item in FALLBACK_TICKETS if item['status'] == 'open') * 18 + sum(1 for item in FALLBACK_EVENTS if item['severity'] == 'high') * 22 + 20)
        else:
            value = 0
        return {'metric_name': metric_name, 'value': int(value)}

    def get_ticket(self, ticket_id: str) -> dict[str, Any] | None:
        if hasattr(self.store, 'get_ticket'):
            return self.store.get_ticket(ticket_id)
        return next((item for item in FALLBACK_TICKETS if item['ticket_id'] == ticket_id), None)

    def plan_sql(self, question: str) -> str:
        """根据自然语言问题生成一条只读 SQL。

        当前实现是规则驱动的，不伪装成大模型 NL2SQL，目的是保证行为真实且稳定。
        """
        normalized = question.lower()
        if any(keyword in normalized for keyword in ['趋势', 'trend', '最近', '故障']):
            return "SELECT system_name, severity, status, ticket_id, duration_minutes, occurred_at FROM incident_events ORDER BY occurred_at DESC LIMIT 10;"
        if any(keyword in normalized for keyword in ['工单', 'ticket', '待处理']):
            return "SELECT id AS ticket_id, system_name, status, owner, severity, summary, created_at FROM tickets ORDER BY created_at DESC LIMIT 10;"
        return "SELECT id AS ticket_id, system_name, status, owner, severity, summary, created_at FROM tickets WHERE system_name = 'payment' ORDER BY created_at DESC LIMIT 5;"

    def analyze_question(self, question: str) -> dict[str, Any]:
        """把“自然语言问题 -> SQL -> 查询结果 -> 摘要”串起来。"""
        sql = self.plan_sql(question)
        rows = self.execute_readonly_sql(sql)
        return {
            'question': question,
            'sql': sql,
            'rows': rows,
            'summary': self._summarize_rows(rows),
        }

    def execute_readonly_sql(self, sql: str) -> list[dict[str, Any]]:
        normalized = sql.strip().lower()
        if not normalized.startswith(('select', 'with')):
            raise ValueError('SQL Agent 只允许执行 SELECT/WITH 只读查询。')
        if hasattr(self.store, 'execute_readonly_sql'):
            return self.store.execute_readonly_sql(sql)
        if 'incident_events' in normalized:
            return FALLBACK_EVENTS
        if 'tickets' in normalized:
            return FALLBACK_TICKETS
        return []

    @staticmethod
    def _summarize_rows(rows: list[dict[str, Any]]) -> str:
        """把 SQL 原始结果压缩成更适合展示的自然语言摘要。"""
        if not rows:
            return '没有查询到符合条件的数据。'
        preview = rows[:3]
        lines = [f'共返回 {len(rows)} 条记录。']
        for row in preview:
            system_name = row.get('system_name', 'unknown')
            status = row.get('status', 'unknown')
            severity = row.get('severity', 'unknown')
            summary = row.get('summary') or row.get('root_cause') or '无补充说明'
            lines.append(f'- 系统 {system_name}，状态 {status}，级别 {severity}，摘要：{summary}')
        return '\n'.join(lines)