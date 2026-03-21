# -*- coding: utf-8 -*-
"""
工作流运行入口 - src/agents/runner.py
职责：系统的“点火器”与“收尾员”。
作用：接收用户输入，构建初始状态账本，点火启动 LangGraph，并在运行结束后对产物进行最终质检和保存。
"""

from typing import Any, Dict, List, Optional, Tuple

from src.agents.graph import job_hunter_app # 导入我们刚刚拼装好的主板（编译后的状态机）
from src.config import config
from src.utils.output_formatter import deduplicate_jobs, format_and_save_jobs

DEFAULT_ALLOWED_SITES = [
    "nowcoder.com",
    "zhipin.com",
    "shixiseng.com",
    "liepin.com",
]

def build_initial_state(
    user_input: str,
    target_count: Optional[int] = None,
) -> Dict[str, Any]:
    """
    构建 LangGraph 的初始状态（冷启动账本）。
    图谱在刚启动时，大脑是空白的。我们必须给它塞入第一笔数据（用户的原话）。
    """
    state = {
        # 【核心输入】：用户在网页上敲下的大白话
        "user_input": user_input,
        
        # 预先占位，等待 intent_parser_node（意图解析节点）去把它们填满
        "target_role": "",
        "search_keywords": [],
        
        # 设定 KPI 目标
        "target_count": target_count if target_count is not None else config.TARGET_JOB_COUNT,
        
        # 【初始化累加字段】：
        # 之前在 state.py 里定义为 operator.add 的字段，在这里最好初始化为空列表 []。
        # 这样底层的 LangGraph 引擎在做第一次加法时，就不会因为找不到初始值而报错。
        "collected_jobs": [],
        "current_search_queries": [],
        "used_queries": [],
        "visited_urls": [],
        "current_new_urls": [],
        "scraped_markdowns": [],
        
        # 初始化循环计数器
        "loop_count": 0,
        "allowed_sites": DEFAULT_ALLOWED_SITES,
        "current_site_index": 0,
        "scraped_urls": [],
        
        # 注意：像 validated_urls 这种我们在 state.py 里标记了 NotRequired 的字段，
        # 在这里不写也是完全合法的，展示了极好的类型工程规范。
    }
    return state


def run_pipeline(
    user_input: str,
    target_count: Optional[int] = None,
    output_dir: str = ".",
) -> Tuple[Optional[str], Optional[str], str]:
    """
    黑盒调用接口：外部世界只需要调用这个函数，不需要管里面爬虫怎么跑、大模型怎么想。
    根据用户输入执行完整流水线：意图解析 → 搜索 → 评估 → 返回结果。
    参数:
    user_input: 用户自然语言输入（如"帮我找ai工程师的实习岗位50条"）
    target_count: 期望收集的岗位数量，默认使用 config
    output_dir: 输出目录，默认当前目录
    返回:
    (csv_path, json_path, summary_message)  
    """
    # 1. 准备冷启动账本
    initial_state = build_initial_state(
        user_input=user_input,
        target_count=target_count,
    )
    
    # LangGraph 默认有一个死循环保护机制：如果图谱循环超过 25 次就会直接抛出 GraphRecursionError 崩溃。
    # 我们在这里通过 config 显式接管了这个配置，确保 Agent 有足够的轮次去“肝”出 50 个岗位。
    run_config = {"recursion_limit": config.RECURSION_LIMIT}

    try:
        # 2. ⚡️ 正式点火！启动 Agent 状态机
        # invoke 会一直阻塞等待，直到图谱走向 END 节点，或者触发 recursion_limit
        final_state = job_hunter_app.invoke(initial_state, config=run_config)
    except Exception as e:
        # 捕获系统级崩溃（比如断网、大模型欠费）
        return None, None, f"系统运行出错：{e}"

    # 3. 提取最终战利品
    valid_jobs_list = final_state.get("collected_jobs", [])
    
    # 【最后一道防线】：出厂前做最后一次物理去重。
    # 尽管图谱内部已经做了极其严密的去重，但在正式落盘前，再用 Python 脚本洗一遍数据是极度严谨的表现。
    valid_jobs_list = deduplicate_jobs(valid_jobs_list)
    total_found = len(valid_jobs_list)

    if total_found == 0:
        return None, None, "任务结束。未找到符合要求的岗位数据（可能是搜索词太偏门，或都被安全策略拦截）。"

    # 4. 调用输出工具，将内存里的字典写入硬盘的 CSV 和 JSON 文件
    csv_path, json_path = format_and_save_jobs(valid_jobs_list, output_dir=output_dir)
    
    # 5. 拼装好汇报话术，返回给前端 Gradio
    summary = f"🎉 任务圆满完成！已为你收集 {total_found} 条有效岗位数据。\n\n📂 文件已生成：\n- CSV 报表: {csv_path}\n- JSON 数据: {json_path}"
    
    return csv_path, json_path, summary