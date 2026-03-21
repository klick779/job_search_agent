# -*- coding: utf-8 -*-
"""
语义评估节点 - src/agents/nodes/semantic_evaluator_node.py
职责：将杂乱的 Markdown 文本交给大模型进行结构化提取（填表），并剔除不符合要求的岗位。
"""

from typing import Dict
from src.agents.state import AgentState
from src.tools.parser_tool import parse_page_to_job

def _normalize_url(url: str) -> str:
    """标准化 URL：去除末尾斜杠，统一格式，防止同一个网址被识别成两个"""
    return url.rstrip("/")

def semantic_evaluator_node(state: AgentState) -> Dict:
    """解析网页内容，提取结构化 JobInfo"""
    
    scraped_items = state.get("scraped_markdowns", [])
    previous_jobs = state.get("collected_jobs", [])
    target_role = state.get("target_role", "")

    # 【亮点 1：构建全局历史防重集合】
    # 把之前所有轮次已经收集到的有效岗位 URL 提取出来，做成一个 Set。
    # 这确保了即使跨了多个搜索轮次，也不会收录同一个岗位。
    existing_urls = {_normalize_url(job.get("job_url", "")) for job in previous_jobs if job.get("job_url")}

    new_valid_jobs = []
    
    # 遍历爬虫刚抓回来的每一篇网页文本
    for item in scraped_items:
        
        # 爬虫底层会标记一些死链，这里直接过滤，给大模型省 Token
        if not item.get("is_valid", True):
            print(f"  [过滤无效] {item['url']} - 页面已失效")
            continue
            
        # 【亮点 2：调用 LLM 施展魔法】
        # 这里会触发大模型推理，判断 is_valid_role。如果大模型觉得这不是我们要的岗，会返回 None
        parsed = parse_page_to_job(item["markdown"], item["url"], target_role=target_role)
        
        if parsed:
            job_url = _normalize_url(parsed.get("job_url", ""))
            
            # 【亮点 3：本轮内防重拦截】
            # 万一爬虫在这一轮里抓了两个指向同一个岗位的 URL（比如带有不同追踪参数），
            # 只要进过一次 existing_urls，第二次就会被拦下。
            if job_url and job_url in existing_urls:
                continue
                
            # 确认为全新且有效的岗位，收入囊中！
            new_valid_jobs.append(parsed)
            
            # 立刻把新 URL 加入查重集合，防止后面的循环遇到双胞胎
            existing_urls.add(job_url)

    print(f"  [语义评估] 成功提取 {len(new_valid_jobs)} 个符合要求的新岗位。")

    # 因为状态机里的 collected_jobs 配置了 operator.add，
    # 所以我们只需要把本轮的 new_valid_jobs 传出去，LangGraph 会自动把它们追加到总表里！
    return {"collected_jobs": new_valid_jobs}