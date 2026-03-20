# -*- coding: utf-8 -*-
"""
LangGraph 状态机定义 - src/agents/graph.py
职责：定义 Agent 的工作流（Workflow），控制数据在各个节点之间的流向。
核心亮点：构建了一个带有“条件中断”的循环有向图（Cyclic Graph），赋予 Agent 自主重试的能力。
"""

from typing import Literal
from langgraph.graph import StateGraph, START, END

# 引入我们定义好的“全局账本”
from src.agents.state import AgentState
# 引入流水线上的 6 个“工人”
from src.agents.nodes import (
    intent_parser_node,
    query_planner_node,
    job_searcher_node,
    url_validator_node,
    detail_scraper_node,
    semantic_evaluator_node
)
from src.config import config


# ==========================================
# 模块 1：系统的大脑刹车（路由守卫）
# ==========================================
def check_completion_router(state: AgentState) -> Literal["query_planner", "end"]:
    """
    路由守卫（Conditional Edge / Router）。
    作用：每次评估完一批岗位后，负责检查 KPI 是否达标，决定是“继续加班”还是“打卡下班”。
    """
    # 查账本：现在抓到多少个了？目标是多少个？现在是第几轮？
    current_count = len(state.get("collected_jobs", []))
    target_count = state.get("target_count", 50)
    loop_count = state.get("loop_count", 0)
    MAX_LOOPS = config.MAX_LOOP_COUNT # 从配置文件读取最大安全循环次数（比如 10 次）
    
    # 打印进度条，方便在终端里观察 Agent 的挣扎过程
    print(f"\n--- [状态机监控] 达成：{current_count}/{target_count}，轮数：{loop_count}/{MAX_LOOPS} ---")
    
    # 刹车条件 1：KPI 达标，光荣下班
    if current_count >= target_count:
        print("  ✅ 目标数量达成，终止工作流。")
        return "end" # 这里的返回值必须和下面 router 字典里的 key 对应
    
    # 刹车条件 2：死循环保护（系统熔断机制）
    # 如果搜了 10 轮都没凑够（可能全网就没这么多岗位），强制下班，防止破产
    if loop_count >= MAX_LOOPS:
        print(f"  ⚠️ 达到最大安全轮数 {MAX_LOOPS}，触发熔断保护，强制终止。")
        return "end"
    
    # 如果没达标，也没超时，那就指挥图谱流回到“查询规划节点”，重新想词儿继续搜！
    return "query_planner"


# ==========================================
# 模块 2：（图谱构建）
# ==========================================
def create_job_hunter_graph() -> StateGraph:
    """创建并编译 LangGraph 状态机"""
    
    # 1. 初始化一张图，并把全局账本 (AgentState) 交给图谱管理
    workflow = StateGraph(AgentState)
    
    # 2. 招募工人（将函数注册为图谱的节点）
    # 参数1：节点的名字（随便起）  参数2：对应的 Python 函数
    workflow.add_node("intent_parser", intent_parser_node)
    workflow.add_node("query_planner", query_planner_node)
    workflow.add_node("job_searcher", job_searcher_node)
    workflow.add_node("url_validator", url_validator_node)  # 我们省钱的守门员
    workflow.add_node("detail_scraper", detail_scraper_node)
    workflow.add_node("semantic_evaluator", semantic_evaluator_node)
    
    # 3. 铺设单向流水线（定义静态图的流向）
    # START 是系统内置的虚拟起点。程序一启动，立刻把数据喂给意图解析节点
    workflow.add_edge(START, "intent_parser")
    workflow.add_edge("intent_parser", "query_planner")
    workflow.add_edge("query_planner", "job_searcher")
    workflow.add_edge("job_searcher", "url_validator")  
    workflow.add_edge("url_validator", "detail_scraper")  
    workflow.add_edge("detail_scraper", "semantic_evaluator")
    
    # 4. 铺设动态分叉路口（定义条件边）
    # 这就是 Agent 被称为“智能体”的原因——它能根据运行时的数据自己决定下一步去哪。
    workflow.add_conditional_edges(
        "semantic_evaluator",      # 从哪个节点出来后开始做决定？
        check_completion_router,   # 用哪个函数来做决定？
        {
            # 翻译守卫函数的返回值：
            # 如果守卫返回 "query_planner"，就把数据送给 query_planner 节点（形成闭环）
            "query_planner": "query_planner", 
            # 如果守卫返回 "end"，就把数据送给系统的内置终点 END（图谱运行结束）
            "end": END                        
        }
    )
    
    # 5. 编译成可执行的程序（就像 C++ 的 compile）
    return workflow.compile()


# 实例化最终的 Agent，供其他文件导入使用
job_hunter_app = create_job_hunter_graph()