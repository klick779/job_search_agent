# -*- coding: utf-8 -*-
"""
系统启动入口 - main.py
该文件是整个 Agentic AI 求职助手系统的执行入口。
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.agents.graph import job_hunter_app
from src.utils.output_formatter import format_and_save_jobs, deduplicate_jobs
from src.config import config


def main():
    """启动 Agentic AI 自动化求职助手系统"""
    print("==================================================")
    print("       启动 Agentic AI 自动化求职助手系统        ")
    print("==================================================")
    print(f"目标：收集 {config.TARGET_JOB_COUNT} 个 岗位信息")
    print(f"最大迭代次数：{config.MAX_LOOP_COUNT}")
    print("==================================================\n")
    
    # 初始状态
    initial_state = {
        "target_count": config.TARGET_JOB_COUNT,
        "collected_jobs": [],
        "current_search_queries": [],
        "used_queries": [],
        "visited_urls": [],
        "current_new_urls": [],
        "scraped_markdowns": [],
        "loop_count": 0,
        "allowed_sites": [
            "nowcoder.com",
            "shixiseng.com",
            "zhipin.com",
            "lagou.com",
            "liepin.com",
        ],
        "current_site_index": 0,
        "scraped_urls": [],
    }
    
    run_config = {"recursion_limit": config.RECURSION_LIMIT}
    
    try:
        final_state = job_hunter_app.invoke(initial_state, config=run_config)
    except Exception as e:
        print(f"运行错误：{e}")
        import traceback
        traceback.print_exc()
        return
    
    # 结果处理
    valid_jobs_list = final_state.get("collected_jobs", [])
    valid_jobs_list = deduplicate_jobs(valid_jobs_list)
    total_found = len(valid_jobs_list)
    
    if total_found == 0:
        print("运行结束。未能找到任何符合要求的岗位数据。")
        return
    
    print(f"\n系统运转完毕！去重后共 {total_found} 条岗位数据。\n")
    
    format_and_save_jobs(valid_jobs_list)
    
    print("\n==================================================")
    print("                    运行完成                      ")
    print("==================================================")


if __name__ == "__main__":
    main()
