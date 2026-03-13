# -*- coding: utf-8 -*-
"""
工作流运行入口 - src/agents/runner.py
接收用户输入，构建初始状态，执行 LangGraph 图，返回最终状态与输出路径。
"""

from typing import Any, Dict, List, Optional, Tuple

from src.agents.graph import job_hunter_app
from src.config import config
from src.utils.output_formatter import deduplicate_jobs, format_and_save_jobs


DEFAULT_ALLOWED_SITES = [
    "nowcoder.com",
    "shixiseng.com",
    "zhipin.com",
    "liepin.com",
]


def build_initial_state(
    user_input: str,
    target_count: Optional[int] = None,
) -> Dict[str, Any]:
    """
    构建 LangGraph 初始状态。
    意图解析将在 LangGraph 内部完成。
    """
    state = {
        # 用户原始输入
        "user_input": user_input,
        
        # 意图解析结果（初始为空，由 intent_parser_node 填充）
        "target_role": "",
        "search_keywords": [],
        
        # 搜索相关
        "target_count": target_count if target_count is not None else config.TARGET_JOB_COUNT,
        "collected_jobs": [],
        "current_search_queries": [],
        "used_queries": [],
        "visited_urls": [],
        "current_new_urls": [],
        "scraped_markdowns": [],
        "loop_count": 0,
        "allowed_sites": DEFAULT_ALLOWED_SITES,
        "current_site_index": 0,
        "scraped_urls": [],
    }
    return state


def run_pipeline(
    user_input: str,
    target_count: Optional[int] = None,
    output_dir: str = ".",
) -> Tuple[Optional[str], Optional[str], str]:
    """
    根据用户输入执行完整流水线：意图解析 → 搜索 → 评估 → 返回结果。

    参数:
        user_input: 用户自然语言输入（如"帮我找交通运输的实习"）
        target_count: 期望收集的岗位数量，默认使用 config
        output_dir: 输出目录，默认当前目录

    返回:
        (csv_path, json_path, summary_message)
    """
    initial_state = build_initial_state(
        user_input=user_input,
        target_count=target_count,
    )

    run_config = {"recursion_limit": config.RECURSION_LIMIT}

    try:
        final_state = job_hunter_app.invoke(initial_state, config=run_config)
    except Exception as e:
        return None, None, f"运行出错：{e}"

    valid_jobs_list = final_state.get("collected_jobs", [])
    valid_jobs_list = deduplicate_jobs(valid_jobs_list)
    total_found = len(valid_jobs_list)

    if total_found == 0:
        return None, None, "未找到符合要求的岗位数据。"

    csv_path, json_path = format_and_save_jobs(valid_jobs_list, output_dir=output_dir)
    summary = f"已收集 {total_found} 条岗位数据。文件已生成：\n- CSV: {csv_path}\n- JSON: {json_path}"
    return csv_path, json_path, summary
