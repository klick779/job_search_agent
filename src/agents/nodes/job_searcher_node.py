# -*- coding: utf-8 -*-
"""
岗位搜索节点 - src/agents/nodes/job_searcher_node.py
职责：调用 Tavily 搜索工具，基于规划好的关键词获取岗位 URL。
作用：执行真实的外部网络搜索，并进行严格的 URL 去重，防止重复抓取浪费时间和金钱。
"""

from typing import Dict

from src.agents.state import AgentState
from src.tools.search_tool import targeted_job_search # 导入我们之前写好的带防御墙的搜索工具


DEFAULT_ALLOWED_SITES = [
    "nowcoder.com",
    "shixiseng.com",
    "zhipin.com",
    "liepin.com",
]

def _normalize_url(url: str) -> str:
    """
    标准化 URL（清洗黑魔法）
    为什么要做这个？因为 "https://abc.com/job" 和 "https://abc.com/job/"
    在机器看来是两个网址，但其实指向同一个页面。去掉末尾的斜杠可以大幅降低重复率。
    """
    return url.rstrip("/")


def job_searcher_node(state: AgentState) -> Dict:
    """搜索执行节点核心逻辑"""
    
    found_urls = []       # 准备一个空列表，装这轮新找到的纯净 URL
    found_normalized = set() # 用一个集合（Set）来加速查重（O(1) 复杂度）
    found_snippets = []   # 准备装搜索结果的摘要（给后面的 url_validator 大模型做判断用）
    
    # --- 1. 构建历史黑名单（去重防御线） ---
    # 把之前爬过的、访问过的 URL 全部拿出来，洗干净（标准化）后扔进黑名单集合
    scraped_urls_set = {_normalize_url(u) for u in state.get("scraped_urls", [])}
    visited_urls_set = {_normalize_url(u) for u in state.get("visited_urls", [])}
    
    # Python 集合魔法：使用 | 符号将两个集合合并成一个终极黑名单
    all_existing_urls = scraped_urls_set | visited_urls_set
    
    # --- 2. 确认去哪个网站搜 ---
    allowed_sites = state.get("allowed_sites", DEFAULT_ALLOWED_SITES)
    current_site_index = state.get("current_site_index", 0)
    current_site = allowed_sites[current_site_index] # 比如这轮轮到了 "nowcoder.com"
    
    # --- 3. 遍历查询大脑给出的 3 个搜索词 ---
    for query in state["current_search_queries"]:
        try:
            # 调用 @tool 包装的外部搜索接口
            result = targeted_job_search.invoke({
                "keyword": query,
                "target_domain": current_site
            })
            
            # 如果搜索失败（比如我们之前在 search_tool 里写的 API 限流、超时）
            if not result["success"]:
                continue # 不报错，直接跳过这个词，搜下一个词
            
            # 剥离出 URL 和 摘要
            urls = result.get("urls", [])
            snippets = result.get("snippets", [])
            
            # --- 4. 逐个鉴别新找到的 URL ---
            for idx, url in enumerate(urls):
                normalized = _normalize_url(url)
                
                # 【核心拦截】：如果在历史黑名单里，或者在这轮刚才已经加上了，直接扔掉！
                if normalized in all_existing_urls or normalized in found_normalized:
                    continue
                    
                # 存入纯净白名单
                found_urls.append(url)
                found_normalized.add(normalized)
                
                # 配对保存摘要（防越界处理：确保 snippet 索引不超出范围）
                snippet = snippets[idx] if idx < len(snippets) else ""
                found_snippets.append({
                    "url": url,
                    "title": snippet.split("\n")[0] if snippet else "",  # 粗略提取第一行当标题
                    "snippet": snippet
                })
        except Exception as e:
            # 如果 invoke 发生了极端的未知崩溃，记录日志并跳过
            print(f"⚠️ [搜索节点异常] 词:{query}, 站:{current_site}, 错:{e}")
            continue
    
    # --- 5. 更新全局状态账本 ---
    return {
        "visited_urls": found_urls,         # 【正确】因为有 operator.add，会追加到历史记录中
        "current_new_urls": found_urls,     # 【正确】覆盖本轮新 URL，供下一个节点使用
        "current_search_snippets": found_snippets, # 【正确】传递摘要供大模型验证
        "current_site_index": current_site_index,  # 其实不返回也可以，因为没修改，但返回也没错
    }