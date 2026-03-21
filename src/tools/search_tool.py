# -*- coding: utf-8 -*-
"""
搜索工具模块 - src/tools/search_tool.py
该模块封装外部搜索引擎 API（Tavily），提供定向搜索接口。
作用：利用 Tavily 的 include_domains 参数定向搜索特定招聘网站。
"""

from typing import List, Dict, Any # 类型提示标配
from langchain_core.tools import tool # 导入 LangChain 的神器：@tool 装饰器
from langchain_community.tools import TavilySearchResults # 导入 LangChain 封装好的 Tavily 搜索类

from src.config import get_tavily_api_key, config # 导入你的配置管理模块

# @tool 装饰器极其重要！
# 它会把下面这个普通的 Python 函数，连同它的名字、参数、和多行注释（Docstring），
# 一起打包翻译成大模型能看懂的 JSON Schema。
# 大模型就是看着这段注释，才知道什么时候该调用这个工具，以及该传什么参数。
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
    query = keyword  # 将关键词赋给 query 变量
    urls: List[str] = []        # 初始化空列表，准备装载抓到的 URL
    snippets: List[str] = []     # 初始化空列表，准备装载搜索结果的摘要（供后续大模型验证使用）   
    
    # 开启危险的 I/O 操作防线。凡是调用外部网络 API，必须加 try-except！
    try:
        api_key = get_tavily_api_key() # 动态获取 API Key
        
        # 实例化 Tavily 搜索工具
        tavily_tool = TavilySearchResults(
            api_key=api_key,
            max_results=config.MAX_SEARCH_RESULTS, # 从配置文件读取最大返回条数（比如一次搜20条）
            include_domains=[target_domain],       # 将搜索范围死死限制在指定的域名内（比如只搜牛客网）
            include_raw_content=False              # 不抓取完整的原始 HTML，节省带宽和内存，把重活交给后面的专业爬虫 Crawl4AI
        )
        
        # 正式向 Tavily 服务器发起搜索请求，返回的是一个字典列表
        raw_results = tavily_tool.invoke(query)
        
        # 遍历返回的结果
        for item in raw_results:
            url = item.get("url", "")
            # 尝试获取内容摘要，如果没有 content，就退而求其次用 title
            snippet = item.get("content") or item.get("title", "")
            
            if url: # 如果拿到了有效的 URL
                urls.append(url)
                snippets.append(snippet)
        
        # 搜索成功！返回结构化的状态字典，供 Agent 的状态机（AgentState）流转使用
        return {
            "success": True,
            "urls": urls,
            "snippets": snippets,
            "target_domain": target_domain,
            "query": query
        }
    # --- 异常捕获与故障隔离区 ---
    except Exception as e:
        error_msg = str(e)           # 获取错误详情文本
        error_type = type(e).__name__ # 获取错误类型的名字（比如 TimeoutError）
        
        # 打印日志，保留“犯罪现场”，方便开发者排查
        print(f"    [搜索异常] domain:{target_domain} 关键词:{keyword}")
        print(f"    错误类型: {error_type}, 详情: {error_msg}")
        
        # 1. 拦截 API 限流异常（Rate Limit）
        if "RateLimit" in error_type or "429" in error_msg:
            return {
                "success": False,
                "urls": [],
                "snippets": [],
                "error": f"Tavily API 限流 (RateLimitError)",
                "target_domain": target_domain,
                "query": query
            }
        # 2. 拦截网络超时异常
        elif "timeout" in error_msg.lower() or "Timeout" in error_type:
            return {
                "success": False,
                "urls": [],
                "snippets": [],
                "error": f"搜索请求超时",
                "target_domain": target_domain,
                "query": query
            }
        # 3. 拦截 API Key 未配置的低级错误
        elif "API key" in error_msg or "api_key" in error_msg.lower():
            return {
                "success": False,
                "urls": [],
                "snippets": [],
                "error": f"Tavily API Key 未配置",
                "target_domain": target_domain,
                "query": query
            }
        
        # 4. 兜底拦截其他所有未知的奇葩异常
        # 只要走到这一步，必定是系统级故障，success 必须强制为 False！
        else:
            return {
                "success": False, # 坚持底线，不掩盖错误
                "urls": [],
                "snippets": [],
                "error": f"搜索发生未知的系统级故障: {error_type} - {error_msg[:100]}",
                "target_domain": target_domain,
                "query": query
            }