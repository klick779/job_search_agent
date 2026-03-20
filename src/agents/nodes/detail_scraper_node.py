# -*- coding: utf-8 -*-
"""
详情抓取节点 - src/agents/nodes/detail_scraper_node.py
职责：调用 Crawl4AI 无头浏览器，去网页上真正把文字扒下来。
"""

from typing import Dict
from src.agents.state import AgentState
from src.tools.scraper_tool import scrape_urls

def detail_scraper_node(state: AgentState) -> Dict:
    """抓取网页内容的核心流程"""

    if "validated_urls" in state:
        urls_to_scrape = state.get("validated_urls")
    else:
        # 万一系统没配置验证节点，兜底使用最初的搜索结果
        urls_to_scrape = state.get("current_new_urls", [])
    
    # 如果没有要爬的链接（比如全被验证节点拦截了），直接下班
    if not urls_to_scrape:
        print("  [详情爬取] 本轮没有存活的有效 URL，跳过爬取。")
        return {
            "scraped_markdowns": [],
            "scraped_urls": [] # 返回空增量
        }
    
    print(f"  [详情爬取] 准备爬取 {len(urls_to_scrape)} 个URL...")
    
    # 调动异步爬虫开始干活
    scraped_results = scrape_urls(urls_to_scrape)
    
    # 【核心 Bug 修复 2：更新历史账本】
    return {
        "scraped_markdowns": scraped_results, # 把抓回来的 Markdown 传给大模型
        "scraped_urls": urls_to_scrape        # 必须把这些 URL 记入账本，配合 operator.add 实现全局防重！
    }