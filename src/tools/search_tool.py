# -*- coding: utf-8 -*-
"""
搜索工具模块 - src/tools/search_tool.py
该模块封装外部搜索引擎 API（Tavily），提供定向搜索接口。
作用：利用 Tavily 的 include_domains 参数定向搜索特定招聘网站。
"""

from typing import List, Dict, Any
from langchain_core.tools import tool
from langchain_community.tools import TavilySearchResults

from src.config import get_tavily_api_key, config


@tool
def targeted_job_search(keyword: str, target_domain: str) -> Dict[str, Any]:
    """
    定向招聘网站搜索工具（基于 Tavily API）。
    
    作用：利用 Tavily 的 include_domains 参数，定向搜索特定招聘网站的 URL。
    
    参数:
        keyword: 搜索关键词，如 "AI Engineer 实习"
        target_domain: 目标网站域名，如 "nowcoder.com"
    
    返回:
        - success: bool - 搜索是否成功
        - urls: List[str] - 提取到的 URL 列表
        - snippets: List[str] - 对应的页面摘要
        - error: str - 错误信息
        - target_domain: str - 搜索的目标网站域名
        - query: str - 实际执行的搜索查询语句
    """
    query = keyword
    urls = []
    snippets = []
    
    try:
        api_key = get_tavily_api_key()
        
        tavily_tool = TavilySearchResults(
            api_key=api_key,
            max_results=config.MAX_SEARCH_RESULTS,
            include_domains=[target_domain],
            include_answer=True,
            include_raw_content=False
        )
        
        raw_results = tavily_tool.invoke(query)
        
        for item in raw_results:
            url = item.get("url", "")
            snippet = item.get("content") or item.get("title", "")
            
            if url:
                urls.append(url)
                snippets.append(snippet)
        
        return {
            "success": True,
            "urls": urls,
            "snippets": snippets,
            "target_domain": target_domain,
            "query": query
        }
    
    except Exception as e:
        error_msg = str(e)
        error_type = type(e).__name__
        
        print(f"    [搜索异常] domain:{target_domain} 关键词:{keyword}")
        print(f"    错误类型: {error_type}, 详情: {error_msg}")
        
        if "RateLimit" in error_type or "429" in error_msg:
            return {
                "success": False,
                "urls": [],
                "snippets": [],
                "error": f"Tavily API 限流 (RateLimitError)",
                "target_domain": target_domain,
                "query": query
            }
        elif "timeout" in error_msg.lower() or "Timeout" in error_type:
            return {
                "success": False,
                "urls": [],
                "snippets": [],
                "error": f"搜索请求超时",
                "target_domain": target_domain,
                "query": query
            }
        elif "API key" in error_msg or "api_key" in error_msg.lower():
            return {
                "success": False,
                "urls": [],
                "snippets": [],
                "error": f"Tavily API Key 未配置",
                "target_domain": target_domain,
                "query": query
            }
        elif not urls:
            return {
                "success": True,
                "urls": [],
                "snippets": [],
                "error": None,
                "target_domain": target_domain,
                "query": query
            }
        else:
            return {
                "success": False,
                "urls": [],
                "snippets": [],
                "error": f"搜索失败: {error_type} - {error_msg[:100]}",
                "target_domain": target_domain,
                "query": query
            }
