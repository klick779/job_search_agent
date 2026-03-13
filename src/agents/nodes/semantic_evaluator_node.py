# -*- coding: utf-8 -*-
"""
语义评估节点
解析网页内容，判断是否符合用户期望的岗位类型
"""

from typing import Dict

from src.agents.state import AgentState
from src.tools.parser_tool import parse_page_to_job


def _normalize_url(url: str) -> str:
    """标准化 URL"""
    return url.rstrip("/")


def semantic_evaluator_node(state: AgentState) -> Dict:
    """解析网页内容，判断是否符合用户期望的岗位类型"""
    scraped_items = state.get("scraped_markdowns", [])
    previous_jobs = state.get("collected_jobs", [])
    target_role = state.get("target_role", "")

    existing_urls = {_normalize_url(job.get("job_url", "")) for job in previous_jobs if job.get("job_url")}

    new_valid_jobs = []
    for item in scraped_items:
        # 过滤无效 URL（HTTP 状态码异常或抓取失败的页面）
        if not item.get("is_valid", True):
            print(f"  [过滤无效] {item['url']} - 页面已失效")
            continue
            
        parsed = parse_page_to_job(item["markdown"], item["url"], target_role=target_role)
        if parsed:
            job_url = _normalize_url(parsed.get("job_url", ""))
            if job_url and job_url in existing_urls:
                continue
            new_valid_jobs.append(parsed)
            existing_urls.add(job_url)

    return {"collected_jobs": new_valid_jobs}
