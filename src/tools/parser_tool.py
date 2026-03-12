# -*- coding: utf-8 -*-
"""
解析工具模块 - src/tools/parser_tool.py
作用：将抓取到的网页原始内容解析为结构化岗位信息，并做语义判断。
效果：输出符合 JobInfo Schema 的结构化数据，供去重与结果汇总使用。
"""

from typing import Dict, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage

from src.agents.state import JobInfo
from src.agents.prompts import EVALUATOR_SYSTEM_PROMPT, EVALUATOR_USER_TEMPLATE
from src.config import get_llm_client, config


def parse_page_to_job(
    content: str,
    url: str,
    max_content_length: Optional[int] = None,
) -> Optional[Dict]:
    """
    解析单页内容为结构化岗位信息（含语义判断）。
    参数：
        content: 网页 Markdown/文本内容
        url: 该页面对应的 URL
        max_content_length: 内容截断长度，默认使用 config.CONTENT_TRUNCATION_LENGTH
    返回值：符合 JobInfo 的字典，若判定为非 AI 岗位或解析失败则返回 None
    """
    length = max_content_length or config.CONTENT_TRUNCATION_LENGTH
    content_to_eval = content[:length]
    llm = get_llm_client()
    structured_llm = llm.with_structured_output(JobInfo)
    messages = [
        SystemMessage(content=EVALUATOR_SYSTEM_PROMPT),
        HumanMessage(content=EVALUATOR_USER_TEMPLATE.format(content=content_to_eval)),
    ]
    try:
        job_info: JobInfo = structured_llm.invoke(messages)
        if not job_info.is_valid_ai_role:
            return None
        job_info.job_url = url
        return job_info.model_dump()
    except Exception:
        return None


def parse_pages_to_jobs(scraped_items: List[Dict]) -> List[Dict]:
    """
    批量解析多页抓取结果为结构化岗位列表。
    参数：
        scraped_items: 由抓取工具返回的列表，每项为 {"url": str, "markdown": str}
    返回值：通过语义判断的 JobInfo 字典列表
    """
    jobs = []
    for item in scraped_items:
        parsed = parse_page_to_job(item["markdown"], item["url"])
        if parsed:
            jobs.append(parsed)
    return jobs
