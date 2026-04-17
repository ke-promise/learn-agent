from __future__ import annotations

from typing import Any, Awaitable, Callable, TypedDict


class OrchestrationState(TypedDict, total=False):
    """LangGraph 和内置编排共享的状态结构。"""

    user_id: str
    message: str
    intent_type: str
    intent_label: str
    plan: list[str]
    memory_hits: list[dict[str, Any]]
    citations: list[dict[str, Any]]
    tool_results: list[dict[str, Any]]
    trace: list[dict[str, Any]]
    answer: str


def langgraph_status() -> bool:
    """判断当前环境是否安装了 LangGraph。"""
    try:
        import langgraph  # noqa: F401
    except ImportError:
        return False
    return True


def build_langgraph_runner(
    steps: dict[str, Callable[[OrchestrationState], Awaitable[dict[str, Any]] | dict[str, Any]]],
) -> Any | None:
    """按固定顺序构建 LangGraph 工作流。

    这里不做复杂条件边，而是用一条稳定的主链路，
    各节点自己根据 plan 决定“执行还是跳过”。
    """
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError:
        return None

    graph = StateGraph(OrchestrationState)
    for name, func in steps.items():
        graph.add_node(name, func)

    graph.add_edge(START, 'route')
    graph.add_edge('route', 'plan')
    graph.add_edge('plan', 'memory')
    graph.add_edge('memory', 'retrieval')
    graph.add_edge('retrieval', 'tool')
    graph.add_edge('tool', 'compose')
    graph.add_edge('compose', 'report')
    graph.add_edge('report', END)
    return graph.compile()