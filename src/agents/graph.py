# -*- coding: utf-8 -*-
"""
LangGraph 状态机定义
"""

from typing import Literal
from langgraph.graph import StateGraph, START, END

from src.agents.state import AgentState
from src.agents.nodes import (
    intent_parser_node,
    query_planner_node,
    job_searcher_node,
    url_validator_node,
    detail_scraper_node,
    semantic_evaluator_node
)
from src.config import config


def check_completion_router(state: AgentState) -> Literal["query_planner", "end"]:
    """检查是否达到目标或超出循环次数，决定是否继续"""
    current_count = len(state.get("collected_jobs", []))
    target_count = state.get("target_count", 50)
    loop_count = state.get("loop_count", 0)
    MAX_LOOPS = config.MAX_LOOP_COUNT
    
    print(f"\n--- [状态机] 达成：{current_count}/{target_count}，轮数：{loop_count} ---")
    
    if current_count >= target_count:
        print("  目标达成，终止。")
        return "end"
    
    if loop_count >= MAX_LOOPS:
        print(f"  达到最大轮数 {MAX_LOOPS}，强制终止。")
        return "end"
    
    return "query_planner"


def create_job_hunter_graph() -> StateGraph:
    """创建 LangGraph 状态机"""
    workflow = StateGraph(AgentState)
    
    # 添加节点
    workflow.add_node("intent_parser", intent_parser_node)
    workflow.add_node("query_planner", query_planner_node)
    workflow.add_node("job_searcher", job_searcher_node)
    workflow.add_node("url_validator", url_validator_node)  # 新增 URL 验证节点
    workflow.add_node("detail_scraper", detail_scraper_node)
    workflow.add_node("semantic_evaluator", semantic_evaluator_node)
    
    # 定义流程：START → 意图解析 → 查询规划 → 搜索 → URL验证 → 抓取 → 评估 → (循环或结束)
    workflow.add_edge(START, "intent_parser")
    workflow.add_edge("intent_parser", "query_planner")
    workflow.add_edge("query_planner", "job_searcher")
    workflow.add_edge("job_searcher", "url_validator")  # 新增：搜索后进行 URL 验证
    workflow.add_edge("url_validator", "detail_scraper")  # 验证通过后进行抓取
    workflow.add_edge("detail_scraper", "semantic_evaluator")
    
    # 条件边：评估完成后检查是否继续
    workflow.add_conditional_edges(
        "semantic_evaluator",
        check_completion_router,
        {
            "query_planner": "query_planner",
            "end": END
        }
    )
    
    return workflow.compile()


job_hunter_app = create_job_hunter_graph()
