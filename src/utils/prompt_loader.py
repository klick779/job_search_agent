# -*- coding: utf-8 -*-
"""
提示词动态加载工具 - src/utils/prompt_loader.py
运行时从 prompts/*.md 读取内容，作为 System Prompt 或模板使用。
"""

import os
from pathlib import Path
from typing import Optional


def _get_prompts_dir() -> Path:
    """获取 prompts 目录：优先项目根目录下的 prompts，否则为当前文件所在项目根."""
    # 从 src/utils 往上看，项目根 = homework/
    current = Path(__file__).resolve().parent
    root = current.parent.parent  # src -> homework
    prompts_dir = root / "prompts"
    if prompts_dir.exists():
        return prompts_dir
    # 兼容：若在别处运行，尝试 cwd
    cwd_prompts = Path.cwd() / "prompts"
    if cwd_prompts.exists():
        return cwd_prompts
    return root / "prompts"


def load_prompt(name: str, **kwargs: str) -> str:
    """
    根据名称加载 .md 提示词文件内容，并可选地进行变量替换。
    
    参数:
        name: 文件名（不含 .md），如 "evaluator_system"、"query_planner_system"
        **kwargs: 用于 format() 的占位符，如 remaining=10, used_queries_str="..."
    
    返回:
        文件内容字符串；若需替换则对内容执行 .format(**kwargs)。
    
    示例:
        load_prompt("query_planner_system", remaining=30, used_queries_str="无")
        load_prompt("evaluator_system")
    """
    prompts_dir = _get_prompts_dir()
    path = prompts_dir / f"{name}.md"
    if not path.exists():
        raise FileNotFoundError(f"提示词文件不存在: {path}")
    raw = path.read_text(encoding="utf-8")
    # 分离「正文」与「Few-shot 示例」：仅对正文做 format，避免 {} 在示例中报错
    if "---" in raw:
        main_part = raw.split("---")[0].strip()
    else:
        main_part = raw.strip()
    if kwargs:
        return main_part.format(**kwargs)
    return main_part


