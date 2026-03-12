# -*- coding: utf-8 -*-
"""
爬虫工具模块 - src/tools/scraper_tool.py
该模块封装 Crawl4AI 的底层抓取与隐身逻辑，实现对现代招聘网站的高效数据抓取。
作用：绕过反爬虫机制，获取网页的 Markdown 内容，供 LLM 进行语义分析。
效果：返回包含 URL 和 Markdown 内容的字典列表。
"""

import asyncio
from typing import List, Dict
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode


async def execute_stealth_scraping(urls: List[str]) -> List[Dict]:
    """
    基于 Crawl4AI 绕过现代反爬墙，批量抓取网页 Markdown。
    参数：
        urls: 要抓取的 URL 列表
    返回值：包含 url 和 markdown 的字典列表
    效果：开启隐身模式，模拟人类滚动，获取动态加载的内容
    
    核心工程配置说明：
    - enable_stealth: 剔除 navigator.webdriver 标记，混淆浏览器指纹
    - js_scroll: 模拟人类滚动，确保动态加载的内容完全呈现
    - asyncio.sleep: 模拟人类阅读延迟，避免因请求频率过高触发防火墙
    """
    
    # 核心工程配置：反反爬机制（Anti-Bot Evasion）
    browser_config = BrowserConfig(
        headless=True,
        enable_stealth=True,  # 剔除 navigator.webdriver 标记，混淆浏览器指纹
        ignore_https_errors=True  # 容忍部分站点的证书偏差
    )
    
    # 模拟人类滚动，确保动态加载的内容完全呈现
    js_scroll = "window.scrollTo(0, document.body.scrollHeight);"
    
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS,
        js_code=js_scroll,
        wait_for="body"  # 等待 DOM 的 body 元素加载完毕
    )
    
    scraped_data = []
    
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for url in urls:
            try:
                # 节奏控制：模拟人类阅读延迟，避免因请求频率过高触发防火墙
                await asyncio.sleep(2)
                result = await crawler.arun(url=url, config=run_config)
                if result.success and result.markdown:
                    scraped_data.append({
                        "url": url,
                        "markdown": result.markdown  # 获取经过清洗的、对LLM友好的纯净 Markdown
                    })
            except Exception as e:
                print(f"  抓取失败 {url}: {e}，放弃该目标。")
    
    return scraped_data


def scrape_urls(urls: List[str]) -> List[Dict]:
    """
    同步包装函数：调用异步爬虫抓取网页。
    参数：
        urls: 要抓取的 URL 列表
    返回值：包含 url 和 markdown 的字典列表
    效果：在同步执行环境（LangGraph 节点）中调用异步爬虫任务
    """
    return asyncio.run(execute_stealth_scraping(urls))
