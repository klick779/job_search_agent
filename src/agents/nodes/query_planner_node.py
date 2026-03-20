# -*- coding: utf-8 -*-
"""
查询规划节点 - query_planner_node.py
生成搜索关键词，并控制搜索站点的轮换。
"""

from typing import Dict
from langchain_core.messages import HumanMessage 

from src.agents.state import AgentState
from src.config import get_llm_client
from src.utils.prompt_loader import load_prompt


# ---------- 查询规划器提示词 ----------
# 这个函数负责加载提示词，告诉 LLM：“你现在需要想几个新的搜索词了”
def get_query_planner_system_prompt(remaining: int, used_queries_str: str, target_role: str = "通用岗位") -> str:
    """获取查询规划器 System Prompt"""
    try:
        # 尝试动态加载外部 Markdown 文件，注入“还差几个岗位”、“用过哪些词”、“目标岗位”
        return load_prompt("query_planner_system", remaining=remaining, used_queries_str=used_queries_str, target_role=target_role)
    except Exception:
        # 【面试高频考点区】：硬编码的 Fallback（降级方案）
        # 这里把业务逻辑（生成 3 个、逗号分隔）死死绑在了代码里。
        return f"""目标是收集 {remaining} 个{target_role}相关岗位。生成与历史不同的新查询。
历史搜索词: {used_queries_str}
搜索词格式：{{岗位}} 校招/实习/应届生。
禁止包含招聘网站名称。
仅返回逗号分隔的 3 个查询字符串。"""

# 预设的招聘网站轮换池
DEFAULT_ALLOWED_SITES = [
    "nowcoder.com",  # 牛客
    "shixiseng.com", # 实习僧
    "zhipin.com",    # BOSS直聘
    "lagou.com",     # 拉勾
    "liepin.com",    # 猎聘
]

def query_planner_node(state: AgentState) -> Dict:
    """
    生成搜索关键词：
    策略：首次运行直接使用用户原始意图提取的词；后续迭代如果数量不够，则由 LLM 动态编造新词。
    """
    llm = get_llm_client()
    
    # --- 1. 从全局状态账本 (AgentState) 中读取当前进度 ---
    target = state.get("target_count", 50)
    current_count = len(state.get("collected_jobs", []))
    remaining = target - current_count # 计算还差几个岗位达标
    used_queries = state.get("used_queries", []) # 获取已经搜过的词，防止 LLM 重复生成
    loop_count = state.get("loop_count", 0) # 获取当前是第几轮迭代
    target_role = state.get("target_role", "通用岗位")
    
    # --- 2. 站点轮换逻辑（非常聪明的平滑负载均衡） ---
    allowed_sites = state.get("allowed_sites", DEFAULT_ALLOWED_SITES)
    # 取模运算 (%)：如果 loop_count 是 0, 1, 2, 3... 
    # current_site_index 就会在 0, 1, 2, 3, 4, 0, 1... 之间无限循环。
    current_site_index = loop_count % len(allowed_sites)
    
    # --- 3. 冷启动（第一轮抓取） ---
    # 如果是第一轮（loop_count == 0）且没搜过任何词
    if loop_count == 0 and not used_queries:
        intent_keywords = state.get("search_keywords", [])
        if intent_keywords:
            new_queries = intent_keywords[:3] # 取前 3 个词
            # 返回字典去更新 AgentState
            return {
                "current_search_queries": new_queries, # 供这轮搜索使用
                "used_queries": new_queries,           # 【高危 Bug 区，后续详讲】记入历史账本
                "loop_count": loop_count + 1,          # 轮次 +1
                "allowed_sites": allowed_sites,
                "current_site_index": current_site_index,
            }
    
    # --- 4. 迭代生成（第二轮及以后的抓取） ---
    # 代码走到这里，说明第一轮没搜够，需要 LLM 发挥想象力造新词了
    used_queries_str = ", ".join(used_queries) if used_queries else "无"
    
    # 获取组装好的提示词
    prompt = get_query_planner_system_prompt(
        remaining=remaining, 
        used_queries_str=used_queries_str,
        target_role=target_role
    )
    
    # 调用大模型，让它输出逗号分隔的字符串（注意：这里大模型可能会因为幻觉输出废话）
    response = llm.invoke([HumanMessage(content=prompt)])
    
    # 字符串清洗：按逗号切分，并去掉两端的引号和空格
    new_queries = [q.strip().strip('"').strip("'") for q in response.content.split(",") if q.strip()]
    new_queries = new_queries[:3] # 强制只取前 3 个，防止大模型暴走生成太多
    
    
    # 返回并更新图谱状态
    return {
        "current_search_queries": new_queries,
        "used_queries": new_queries, 
        "loop_count": loop_count + 1,
        "allowed_sites": allowed_sites,
        "current_site_index": current_site_index,
    }