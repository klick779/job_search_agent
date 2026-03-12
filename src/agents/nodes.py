# -*- coding: utf-8 -*-
"""
核心智能体节点实现 - src/agents/nodes.py
该模块定义了 LangGraph 状态机中的四个核心节点函数：
1. query_planner_node - 任务规划与动态查询生成
2. job_searcher_node - 多源搜索与页面路由探测
3. detail_scraper_node - 基于Crawl4AI的高阶反爬与自适应抓取
4. semantic_evaluator_node - 语义清洗与数据结构化
作用：实现 Agent 的具体功能逻辑，通过状态机协调完成自动化求职任务。
"""

from typing import Dict
from langchain_core.messages import HumanMessage

from src.agents.state import AgentState
from src.agents.prompts import QUERY_PLANNER_SYSTEM_PROMPT, INITIAL_SEARCH_QUERIES
from src.config import get_llm_client, config
from src.tools.scraper_tool import scrape_urls
from src.tools.parser_tool import parse_page_to_job
from src.tools.search_tool import targeted_job_search


def _normalize_url(url: str) -> str:
    """标准化 URL：去除末尾斜杠，用于去重比较"""
    return url.rstrip("/")


# 预设的招聘网站白名单
# 作用：Agent 会按顺序依次搜索各个网站
# 策略：当某个网站搜不到足够结果时，自动切换到下一个
DEFAULT_ALLOWED_SITES = [
    "nowcoder.com",      # 牛客网 - 互联网校招主力平台
    "shixiseng.com",     # 实习僧 - 实习岗位丰富
    "zhipin.com",        # Boss直聘 - 社招为主但有校招
    "lagou.com",         # 拉勾网 - 互联网招聘
    "liepin.com",        # 猎聘网 - 高端招聘
]


def query_planner_node(state: AgentState) -> Dict:
    """
    状态机节点：根据当前已收集数量与历史查询，动态扩展和优化搜索关键词。
    
    作用：当岗位数量不足目标数量时，Agent 通过分析过往的失败查询，
          利用大模型自主生成全新的搜索策略，并从白名单中选择当前目标网站。
    
    效果：实现多网站切换和迭代搜索，防止陷入死循环。
    
    1. 获取当前已收集的岗位数量，计算还差多少达到目标
    2. 将上下文信息传给 LLM，由 LLM 自主决定搜索方向和关键词
    3. 从 allowed_sites[current_site_index] 获取当前目标网站
    4. 返回更新后的状态
    
    特殊处理：
    - 首次运行时（used_queries 为空且 loop_count 为 0）：
      使用预设的初始查询列表
    """
    llm = get_llm_client()
    target = state.get("target_count", 50)
    current_count = len(state.get("collected_jobs", []))
    remaining = target - current_count
    used_queries = state.get("used_queries", [])
    
    # 获取定向搜索相关状态
    allowed_sites = state.get("allowed_sites", DEFAULT_ALLOWED_SITES)
    loop_count = state.get("loop_count", 0)
    
    # 【核心修改点：强制轮询策略】
    # 利用 loop_count 作为驱动器，每跑一轮循环，强制切换到下一个网站
    # 例如：第0轮牛客，第1轮实习僧，第2轮拉勾，第3轮又回到牛客...
    current_site_index = loop_count % len(allowed_sites)
    current_site = allowed_sites[current_site_index]
    
    # 确保 current_site_index 在有效范围内
    if current_site_index >= len(allowed_sites):
        current_site_index = 0  # 循环回到第一个网站
        current_site = allowed_sites[current_site_index]
    
    used_queries_str = ", ".join(used_queries) if used_queries else "无"
    
    # 首次运行时的特殊处理：使用预设的初始查询
    if len(used_queries) == 0 and state.get("loop_count", 0) == 0:
        print(f"[Query Planner] 首次运行，使用初始搜索策略...")
        print(f"[Query Planner] 当前目标网站: {current_site} (索引: {current_site_index})")
        
        new_queries = INITIAL_SEARCH_QUERIES[:3]
        return {
            "current_search_queries": new_queries,
            "used_queries": new_queries,
            "loop_count": state.get("loop_count", 0) + 1,
            "allowed_sites": allowed_sites,
            "current_site_index": current_site_index,
        }
    
    print(f"[Query Planner] 目标: {target}, 当前: {current_count}, 缺口: {remaining}")
    print(f"[Query Planner] 当前目标网站: {current_site} (索引: {current_site_index}/{len(allowed_sites)-1})")
    
    # 构建提示词，调用 LLM 自主生成新的搜索查询
    prompt = QUERY_PLANNER_SYSTEM_PROMPT.format(
        remaining=remaining,
        used_queries_str=used_queries_str
    )
    
    response = llm.invoke([HumanMessage(content=prompt)])
    
    # 清洗 LLM 输出，提取查询词列表
    new_queries = [q.strip().strip('"').strip("'") for q in response.content.split(",") if q.strip()]
    new_queries = new_queries[:3]  # 限制最多3个查询
    
    print(f"[Query Planner] 生成新的搜索策略: {new_queries}")
    
    # 返回字典，LangGraph 会自动通过 Reducer 更新到全局状态
    return {
        "current_search_queries": new_queries,
        "used_queries": new_queries,
        "loop_count": state.get("loop_count", 0) + 1,
        "allowed_sites": allowed_sites,
        "current_site_index": current_site_index,
    }


def job_searcher_node(state: AgentState) -> Dict:
    """
    状态机节点：调用定向搜索工具获取岗位 URL。
    
    作用：使用「定向搜索工具」(targeted_job_search) 获取特定招聘网站的岗位详情 URL 列表。
    
    1. 从状态中获取 current_site_index 和 allowed_sites
    2. 遍历当前搜索关键词列表
    3. 对每个关键词调用 targeted_job_search(site_domain=当前目标网站)
    4. 与 scraped_urls 进行比对，剔除已抓取过的 URL
    5. 如果当前网站返回 0 个新 URL，触发网站切换逻辑 (current_site_index += 1)
    
    效果：返回新发现的 URL 列表，供后续抓取工具使用。
    """
    found_urls = []
    found_normalized = set()  # 本轮已发现的 URL（去重）
    
    # 获取历史已抓取/访问的 URL（用于去重）
    # scraped_urls: 本轮搜索前已抓取过的 URL
    # visited_urls: 历史已访问的 URL（包含抓取失败的）
    scraped_urls_set = {_normalize_url(u) for u in state.get("scraped_urls", [])}
    visited_urls_set = {_normalize_url(u) for u in state.get("visited_urls", [])}
    
    # 合并两个去重集合：既不要重复搜索，也不要重复抓取
    all_existing_urls = scraped_urls_set | visited_urls_set
    
    # 获取定向搜索相关状态
    allowed_sites = state.get("allowed_sites", DEFAULT_ALLOWED_SITES)
    current_site_index = state.get("current_site_index", 0)
    
    # 确保索引在有效范围内
    if current_site_index >= len(allowed_sites):
        current_site_index = 0
    
    current_site = allowed_sites[current_site_index]
    
    print(f"  ============== 定向搜索模式 ==============")
    print(f"  当前目标网站: {current_site} (索引: {current_site_index}/{len(allowed_sites)-1})")
    print(f"  正在对 {len(state['current_search_queries'])} 个关键词进行定向检索...")
    
    # 记录本轮搜索结果统计
    search_stats = {
        "total_found": 0,
        "new_urls": 0,
        "duplicate_urls": 0,
        "failed_searches": 0
    }
    
    # 遍历每个搜索关键词，调用定向搜索
    for query in state["current_search_queries"]:
        try:
            # 调用定向搜索工具
            # 注意：这里传入的是 target_domain（如 "nowcoder.com"），而非完整 URL
            result = targeted_job_search.invoke({
                "keyword": query,
                "target_domain": current_site
            })
            
            if not result["success"]:
                # 搜索失败（网络异常、限流等）
                print(f"    搜索失败 [{current_site}] {query}: {result.get('error', '未知错误')}")
                search_stats["failed_searches"] += 1
                continue
            
            urls = result.get("urls", [])
            search_stats["total_found"] += len(urls)
            
            # URL 去重过滤
            for url in urls:
                normalized = _normalize_url(url)
                # 剔除已抓取/访问过的 URL
                if normalized in all_existing_urls:
                    search_stats["duplicate_urls"] += 1
                    continue
                if normalized in found_normalized:
                    search_stats["duplicate_urls"] += 1
                    continue
                
                # 新发现的 URL
                found_urls.append(url)
                found_normalized.add(normalized)
                search_stats["new_urls"] += 1
                
        except Exception as e:
            print(f"  警告：定向搜索 '{query}' (domain: {current_site}) 异常: {e}")
            search_stats["failed_searches"] += 1
            continue
    
    print(f"  搜索统计: 共发现 {search_stats['total_found']} 个 URL")
    print(f"    - 新增有效 URL: {search_stats['new_urls']}")
    print(f"    - 去重过滤: {search_stats['duplicate_urls']} 个")
    print(f"    - 搜索失败: {search_stats['failed_searches']} 次")
    
    # =============== 网站轮询由 query_planner_node 强制驱动 ===============
    # 此处不再进行条件切换，因为网站切换已由 loop_count 强制轮询
    next_site_index = current_site_index
    
    print(f"  ============== 定向搜索完成 ==============")
    print(f"  成功获取到 {len(found_urls)} 个新的潜在岗位链接。")
    
    # 返回新增的 URL 和相关状态更新
    return {
        "visited_urls": found_urls,  # 加入已访问列表
        "current_new_urls": found_urls,  # 标记本轮新发现的 URL
        "current_site_index": next_site_index,  # 更新网站索引（可能切换）
        "scraped_urls": found_urls,  # 同时加入已抓取列表（用于搜索去重）
    }


def detail_scraper_node(state: AgentState) -> Dict:
    """
    状态机节点：提取最新获取的URL列表，调度异步爬虫进行深度解析。
    作用：使用 Crawl4AI 对搜索结果中的 URL 进行深度抓取，获取页面 Markdown 内容。
    效果：返回包含 URL 和 Markdown 的列表，供语义评估器处理。
    
    实现逻辑：
    1. 取出本轮新发现的 URL 列表（而非历史全部 URL）
    2. 实施批处理截断（每次最多抓取指定数量）
    3. 调用异步爬虫抓取页面
    4. 返回抓取结果
    """
    # 只抓取本轮新发现的 URL，不是全部历史 URL
    current_new_urls = state.get("current_new_urls", [])
    urls_to_scrape = current_new_urls[:config.MAX_SCRAPE_PER_ITERATION]
    
    if not urls_to_scrape:
        print(f"  本轮没有新 URL 需要抓取，跳过爬虫节点。")
        return {"scraped_markdowns": []}
    
    print(f"  启动自适应智能爬虫，准备抓取 {len(urls_to_scrape)} 个网页...")
    
    # 在同步执行环境（LangGraph节点）中挂载并运行异步爬虫任务
    scraped_results = scrape_urls(urls_to_scrape)
    
    print(f"  成功渲染并提取出 {len(scraped_results)} 个网页的 Markdown 数据。")
    return {"scraped_markdowns": scraped_results}


def semantic_evaluator_node(state: AgentState) -> Dict:
    """
    状态机节点：调用解析工具，对抓取结果做语义判断与结构化提取。
    作用：使用「解析工具」将网页 Markdown 转为 JobInfo，并判断是否属于 AI Engineer + 校招/实习。
    效果：每轮发现新岗位时立即去重，只返回真正的新岗位，累加到 collected_jobs。
    """
    scraped_items = state.get("scraped_markdowns", [])
    previous_jobs = state.get("collected_jobs", [])
    
    # 构建已有岗位的 URL 集合（用于去重）
    existing_urls = {_normalize_url(job.get("job_url", "")) for job in previous_jobs if job.get("job_url")}
    print(f"  [去重检查] 历史有效岗位数: {len(previous_jobs)}, 已收录URL数: {len(existing_urls)}")
    
    new_valid_jobs = []
    for item in scraped_items:
        parsed = parse_page_to_job(item["markdown"], item["url"])
        if parsed:
            job_url = _normalize_url(parsed.get("job_url", ""))
            
            # 【关键】本轮内去重：检查是否已存在于历史岗位中
            if job_url and job_url in existing_urls:
                print(f"  [去重拦截] 岗位已存在，跳过: {parsed['title']} @ {parsed['company']}")
                continue
            
            # 是新岗位
            new_valid_jobs.append(parsed)
            existing_urls.add(job_url)  # 加入本轮已发现集合
            print(f"  [新增有效] {parsed['title']} @ {parsed['company']}")
        else:
            print(f"  语义拒绝或解析失败，跳过该页面。")
    
    print(f"  [汇总] 本轮新发现有效岗位: {len(new_valid_jobs)}, 累计有效岗位: {len(previous_jobs) + len(new_valid_jobs)}")
    
    # 返回本轮新发现的岗位，LangGraph 会用 operator.add 自动累加到 collected_jobs
    return {"collected_jobs": new_valid_jobs}
