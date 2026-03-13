# -*- coding: utf-8 -*-
"""
查询规划节点
生成搜索关键词
"""

from typing import Dict

from langchain_core.messages import HumanMessage

from src.agents.state import AgentState
from src.config import get_llm_client
from src.utils.prompt_loader import load_prompt


# ---------- 查询规划器提示词（带 fallback） ----------
def get_query_planner_system_prompt(remaining: int, used_queries_str: str, target_role: str = "通用岗位") -> str:
    """获取查询规划器 System Prompt"""
    try:
        return load_prompt("query_planner_system", remaining=remaining, used_queries_str=used_queries_str, target_role=target_role)
    except Exception:
        return f"""目标是收集 {remaining} 个{target_role}相关岗位。生成与历史不同的新查询。
历史搜索词: {used_queries_str}
搜索词格式：{{岗位}} 校招/实习/应届生。
禁止包含招聘网站名称。
仅返回逗号分隔的 3 个查询字符串。"""


DEFAULT_ALLOWED_SITES = [
    "nowcoder.com",
    "shixiseng.com",
    "zhipin.com",
    "lagou.com",
    "liepin.com",
]


def query_planner_node(state: AgentState) -> Dict:
    """生成搜索关键词：首次使用意图解析的关键词，后续由 LLM 生成"""
    llm = get_llm_client()
    target = state.get("target_count", 50)
    current_count = len(state.get("collected_jobs", []))
    remaining = target - current_count
    used_queries = state.get("used_queries", [])
    loop_count = state.get("loop_count", 0)
    
    allowed_sites = state.get("allowed_sites", DEFAULT_ALLOWED_SITES)
    current_site_index = loop_count % len(allowed_sites)
    current_site = allowed_sites[current_site_index]
    target_role = state.get("target_role", "通用岗位")
    
    # 首次运行：使用意图解析的关键词
    if loop_count == 0 and not used_queries:
        intent_keywords = state.get("search_keywords", [])
        if intent_keywords:
            new_queries = intent_keywords[:3]
            return {
                "current_search_queries": new_queries,
                "used_queries": new_queries,
                "loop_count": loop_count + 1,
                "allowed_sites": allowed_sites,
                "current_site_index": current_site_index,
            }
    
    # 后续运行：LLM 生成新关键词
    used_queries_str = ", ".join(used_queries) if used_queries else "无"
    prompt = get_query_planner_system_prompt(
        remaining=remaining, 
        used_queries_str=used_queries_str,
        target_role=target_role
    )
    
    response = llm.invoke([HumanMessage(content=prompt)])
    new_queries = [q.strip().strip('"').strip("'") for q in response.content.split(",") if q.strip()]
    new_queries = new_queries[:3]
    
    return {
        "current_search_queries": new_queries,
        "used_queries": new_queries,
        "loop_count": loop_count + 1,
        "allowed_sites": allowed_sites,
        "current_site_index": current_site_index,
    }
