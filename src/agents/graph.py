# -*- coding: utf-8 -*-
"""
智能体流转控制与防死循环路由机制 - src/agents/graph.py
该模块负责将各个独立的功能节点串联成完整的 LangGraph 工作流。
包含：条件路由器（Conditional Router）实现和图架构编译与初始化。
作用：实现 Agent 的闭环迭代逻辑，防止无限死循环。
效果：通过条件边缘回路（add_conditional_edges）完成从"静态爬虫"向"闭环自动化系统"的跨越。
"""

from typing import Literal
from langgraph.graph import StateGraph, START, END

from src.agents.state import AgentState
from src.agents.nodes import (
    query_planner_node,
    job_searcher_node,
    detail_scraper_node,
    semantic_evaluator_node
)
from src.config import config


def check_completion_router(state: AgentState) -> Literal["query_planner", "end"]:
    """
    边缘判定逻辑：检视当前状态，决定是将控制权交还给规划器开启新一轮迭代，还是安全终止工作流。
    作用：这是 Agent 系统的"大脑"，直接解答了面试官关于"如何防止 Agent 陷入无限死循环"的考量。
    效果：根据已收集岗位数量和循环次数，决定是否继续搜索或终止任务。
    
    实现逻辑：
    1. 检查当前已收集的岗位数量是否达到目标
    2. 检查循环次数是否超过最大容忍阈值
    3. 根据检查结果返回下一个节点名称
    """
    current_count = len(state.get("collected_jobs", []))
    target_count = state.get("target_count", 50)
    loop_count = state.get("loop_count", 0)
    
    # 全局动态参数：安全熔断最大容忍圈数
    MAX_LOOPS = config.MAX_LOOP_COUNT
    
    print(f"\n--- [状态机评估] 当前达成率：{current_count}/{target_count}，当前迭代轮数：{loop_count} ---")
    
    # 成功条件达成
    if current_count >= target_count:
        print("  目标岗位数量已达成！准备终止网络。")
        return "end"
    
    # 死循环熔断强制干预
    if loop_count >= MAX_LOOPS:
        print(f"  严重警告：触发防死循环熔断保护！执行轮数超越阈值 ({MAX_LOOPS})。强制中止作业。")
        return "end"
    
    print("  目标尚未完成，状态发回任务规划器进行新一轮自适应扩展...")
    return "query_planner"


def create_job_hunter_graph() -> StateGraph:
    """
    创建并编译 LangGraph 状态机。
    作用：构建完整的 Agent 工作流，定义节点、边和条件路由。
    返回值：编译后的可执行 StateGraph 应用实例
    效果：将四个核心节点连接成闭环的自动化求职系统。

    """
    # 实例化强类型的状态图容器
    workflow = StateGraph(AgentState)
    
    # 注册行动节点集群
    workflow.add_node("query_planner", query_planner_node)
    workflow.add_node("job_searcher", job_searcher_node)
    workflow.add_node("detail_scraper", detail_scraper_node)
    workflow.add_node("semantic_evaluator", semantic_evaluator_node)
    
    # 建立固定流转有向边 (Static Edges)
    # 作用：定义节点的固定执行顺序
    workflow.add_edge(START, "query_planner")
    workflow.add_edge("query_planner", "job_searcher")
    workflow.add_edge("job_searcher", "detail_scraper")
    workflow.add_edge("detail_scraper", "semantic_evaluator")
    
    # 配置条件反馈路由 (Conditional Edges) 以构建系统闭环
    # 作用：实现"搜索->评估->不足则重试"的闭环迭代逻辑
    workflow.add_conditional_edges(
        "semantic_evaluator",
        check_completion_router,
        {
            "query_planner": "query_planner",  # 回流开启新周期
            "end": END  # 中止并输出
        }
    )
    
    # 编译为最终可被调用的可执行应用实例
    job_hunter_app = workflow.compile()
    
    return job_hunter_app


# 创建全局可调用的应用实例
job_hunter_app = create_job_hunter_graph()
