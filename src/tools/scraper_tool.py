# -*- coding: utf-8 -*-
"""
爬虫工具模块 - src/tools/scraper_tool.py
该模块封装 Crawl4AI 的底层抓取与隐身逻辑，实现对现代招聘网站的高效数据抓取。
作用：绕过反爬虫机制，获取网页的 Markdown 内容，供 LLM 进行语义分析。
效果：返回包含 URL 和 Markdown 内容的字典列表。
"""

import asyncio                     # 导入异步库，用于控制等待和并发
from typing import List, Dict      # 导入类型提示，方便知道参数是列表还是字典
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode # 导入核心爬虫组件

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
    
    # 1. 核心工程配置：反反爬机制（Anti-Bot Evasion）
    # BrowserConfig 就像是给浏览器买“装备”和“面具”
    browser_config = BrowserConfig(
        headless=True,            # 无头模式：不弹出浏览器窗口，在后台静默运行
        enable_stealth=True,      # 【核心亮点】开启隐身模式。它会抹除自动化脚本特征（如 navigator.webdriver），
                                  # 让服务器认为你是真人在用浏览器 。
        ignore_https_errors=True  # 忽略 HTTPS 证书错误，防止因为某些小站证书过期导致抓取中断
    )
    
    # 模拟人类滚动：很多网页内容是“下拉才加载”的（懒加载）
    # 这行 JS 代码会让浏览器自动滚到页面最底部，触发所有内容加载 [cite: 503, 516]。
    js_scroll = "window.scrollTo(0, document.body.scrollHeight);"
    
    # CrawlerRunConfig 就像是给浏览器的“操作指南”
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS, # 绕过缓存：不看旧网页，必须请求最新的页面 
        js_code=js_scroll,           # 执行上面的滚动脚本
        wait_for="body"              # 策略：等到网页的 <body> 标签出来再开始抓取，确保页面没白屏
    )
    
    scraped_data = [] # 准备一个“篮子”，装抓好的数据
    
    # 开启爬虫上下文管理器：async with 确保爬完后浏览器能被正确关闭，不占内存
    async with AsyncWebCrawler(config=browser_config) as crawler:
        for url in urls:
            try:
                # 【节奏控制】：每抓一个链接前，强制休息 2 秒。
                # 这一步极其重要！如果不休息，短时间请求过多会触发对方的防火墙拦截 。
                await asyncio.sleep(2) 
                
                # 执行抓取核心动作：arun 是异步运行的意思
                result = await crawler.arun(url=url, config=run_config)
                
                # 尝试获取 HTTP 状态码（比如 200 代表 OK，404 代表没找到） [cite: 258, 313]
                http_status = result.status_code if hasattr(result, 'status_code') else None
                
                # 判断 URL 是否有效：只有 2xx（成功）或 3xx（重定向）才算数 [cite: 258, 330]
                is_url_valid = http_status is None or (200 <= http_status < 400)
                
                # 如果抓取成功，且有 Markdown 内容，且状态码正常
                if result.success and result.markdown and is_url_valid:
                    scraped_data.append({
                        "url": url,
                        "markdown": result.markdown, # Crawl4AI 自动把 HTML 转成了 Markdown
                        "http_status": http_status,
                        "is_valid": True
                    })
                else:
                    # 如果被拦截（比如 403 Forbidden）或页面不存在，打印警告
                    status_info = http_status if http_status else "抓取失败"
                    print(f"  [过滤] {url} -> 状态码: {status_info}")
            except Exception as e:
                # 捕获异常（如网络突然断开），防止程序崩溃
                print(f"  抓取失败 {url}: {e}，放弃该目标。")
    
    return scraped_data # 返回所有抓取成功的字典列表


def scrape_urls(urls: List[str]) -> List[Dict]:
    """
    同步包装函数：调用异步爬虫抓取网页。
    参数：
        urls: 要抓取的 URL 列表
    返回值：包含 url 和 markdown 的字典列表
    效果：在同步执行环境（LangGraph 节点）中调用异步爬虫任务
    同步包装函数：这是为了让主程序（LangGraph）能简单调用这个异步爬虫。
    因为 LangGraph 节点通常是同步的，我们用 asyncio.run 来架起桥梁。
    """
    return asyncio.run(execute_stealth_scraping(urls))
