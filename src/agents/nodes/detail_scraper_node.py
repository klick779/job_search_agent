# -*- coding: utf-8 -*-
"""
详情抓取节点
抓取网页内容
"""

from typing import Dict

from src.agents.state import AgentState
from src.tools.scraper_tool import scrape_urls


def detail_scraper_node(state: AgentState) -> Dict:
    """抓取网页内容"""
    # 优先使用验证后的 URL，如果没有则使用搜索返回的 URL
    urls_to_scrape = state.get("validated_urls") or state.get("current_new_urls", [])
    # 爬取所有有效 URL
    
    if not urls_to_scrape:
        return {"scraped_markdowns": []}
    
    print(f"  [详情爬取] 准备爬取 {len(urls_to_scrape)} 个URL...")
    
    scraped_results = scrape_urls(urls_to_scrape)
    return {"scraped_markdowns": scraped_results}
