# -*- coding: utf-8 -*-
"""
岗位搜索节点
调用搜索工具获取岗位 URL
"""

from typing import Dict

from src.agents.state import AgentState
from src.tools.search_tool import targeted_job_search


DEFAULT_ALLOWED_SITES = [
    "nowcoder.com",
    "shixiseng.com",
    "zhipin.com",
    "lagou.com",
    "liepin.com",
]


def _normalize_url(url: str) -> str:
    """标准化 URL"""
    return url.rstrip("/")


def job_searcher_node(state: AgentState) -> Dict:
    """调用搜索工具获取岗位 URL"""
    found_urls = []
    found_normalized = set()
    found_snippets = []
    
    scraped_urls_set = {_normalize_url(u) for u in state.get("scraped_urls", [])}
    visited_urls_set = {_normalize_url(u) for u in state.get("visited_urls", [])}
    all_existing_urls = scraped_urls_set | visited_urls_set
    
    allowed_sites = state.get("allowed_sites", DEFAULT_ALLOWED_SITES)
    current_site_index = state.get("current_site_index", 0)
    current_site = allowed_sites[current_site_index]
    
    for query in state["current_search_queries"]:
        try:
            result = targeted_job_search.invoke({
                "keyword": query,
                "target_domain": current_site
            })
            
            if not result["success"]:
                continue
            
            urls = result.get("urls", [])
            snippets = result.get("snippets", [])
            
            for idx, url in enumerate(urls):
                normalized = _normalize_url(url)
                if normalized in all_existing_urls or normalized in found_normalized:
                    continue
                found_urls.append(url)
                found_normalized.add(normalized)
                # 保存搜索结果摘要供 URL 验证使用
                snippet = snippets[idx] if idx < len(snippets) else ""
                found_snippets.append({
                    "url": url,
                    "title": snippet.split("\n")[0] if snippet else "",  # 取第一行作为标题
                    "snippet": snippet
                })
        except Exception as e:
            continue
    
    return {
        "visited_urls": found_urls,
        "current_new_urls": found_urls,
        "current_search_snippets": found_snippets,  # 新增：保存搜索摘要
        "current_site_index": current_site_index,
        "scraped_urls": found_urls,
    }
