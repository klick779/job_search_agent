# -*- coding: utf-8 -*-
"""
解析工具模块 - src/tools/parser_tool.py
作用：将抓取到的网页原始内容解析为结构化岗位信息，并做语义判断。
效果：输出符合 JobInfo Schema 的结构化数据，供去重与结果汇总使用。
"""

from typing import Dict, List, Optional
from langchain_core.messages import SystemMessage, HumanMessage

from src.agents.state import JobInfo
from src.config import get_llm_client, config
from src.utils.prompt_loader import load_prompt


# ---------- 评估器提示词（带 fallback） ----------
def get_evaluator_system_prompt(target_role: str = "通用岗位") -> str:
    """获取评估器 System Prompt"""
    try:
        return load_prompt("evaluator_system", target_role=target_role)
    except Exception:
        return f"""你是技术招聘审查专家。审核网页信息，判断是否符合用户期望的岗位类型（{target_role}），提取结构化标签。
岗位需面向应届生/校招/实习。检测已下线岗位。
按照 Pydantic Schema 输出 JSON。"""


def get_evaluator_user_template(target_role: str = "通用岗位") -> str:
    """获取评估器 User 模板"""
    try:
        return load_prompt("evaluator_user", target_role=target_role)
    except Exception:
        return f"""分析网页内容，判断是否为符合用户期望岗位类型（{target_role}）的校园招聘/实习岗位。
首先检查是否已下线/已关闭。
网页内容：
---
{{content}}
---
按照 Pydantic Schema 输出。"""


def parse_page_to_job(
    content: str,
    url: str,
    target_role: str = "",
    max_content_length: Optional[int] = None,
) -> Optional[Dict]:
    """
    解析单页内容为结构化岗位信息（含语义判断）。
    参数：
        content: 网页 Markdown/文本内容
        url: 该页面对应的 URL
        target_role: 用户期望的岗位类型
        max_content_length: 内容截断长度，默认使用 config.CONTENT_TRUNCATION_LENGTH
    返回值：符合 JobInfo 的字典，若判定为非目标岗位或解析失败则返回 None
    """
    length = max_content_length or config.CONTENT_TRUNCATION_LENGTH
    content_to_eval = content[:length]
    llm = get_llm_client()
    structured_llm = llm.with_structured_output(JobInfo)

    # 获取评估器提示词（已包含 target_role）
    system_prompt = get_evaluator_system_prompt(target_role=target_role)
    user_template = get_evaluator_user_template(target_role=target_role)

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_template.format(content=content_to_eval)),
    ]
    try:
        job_info: JobInfo = structured_llm.invoke(messages)
        if not job_info.is_valid_role:
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
