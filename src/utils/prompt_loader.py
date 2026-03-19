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
    
    # 【划重点】：__file__ 代表当前这个 python 文件自身的绝对路径。
    # resolve() 会解析出完整路径，.parent 就是获取它所在的目录（也就是 src/utils）
    current = Path(__file__).resolve().parent
    
    # 往上退两级：src/utils 的上一级是 src，src 的上一级是项目的根目录
    root = current.parent.parent  
    
    # 用 / 符号把根目录和 "prompts" 文件夹拼接起来，生成类似 "homework/prompts" 的路径
    prompts_dir = root / "prompts"
    
    # exists() 检查这个文件夹在电脑上到底存不存在。如果存在，就直接返回它。
    if prompts_dir.exists():
        return prompts_dir
        
    # 【兼容性处理】：万一你是在其他奇怪的目录下运行程序的怎么办？
    # Path.cwd() 获取的是你当前在终端里敲击命令的那个路径（Current Working Directory）
    cwd_prompts = Path.cwd() / "prompts"
    if cwd_prompts.exists():
        return cwd_prompts
        
    # 如果都找不到，就硬着头皮返回默认拼接的根目录，哪怕后面报错，也能让报错信息指向预期的位置。
    return root / "prompts"


def load_prompt(name: str, **kwargs: str) -> str:
    """
    根据名称加载 .md 提示词文件内容，并可选地进行变量替换。
    
    参数:
        name: 文件名（不含 .md），比如你要加载 "evaluator_system.md"，这里只传 "evaluator_system"
        **kwargs: 这个叫“关键字参数解包”。比如你传入 remaining=10，它就会把提示词里的 {remaining} 替换成 10。
    """
    # 1. 调用上面的函数，拿到存放提示词的文件夹路径
    prompts_dir = _get_prompts_dir()
    
    # 2. 拼接出具体文件的路径，比如 "homework/prompts/evaluator_system.md"
    path = prompts_dir / f"{name}.md"
    
    # 如果文件不存在，立刻抛出错误中断程序，提醒你去建文件
    if not path.exists():
        raise FileNotFoundError(f"提示词文件不存在: {path}")
        
    # 3. 读取整个 Markdown 文件的内容（强制使用 utf-8 编码，防止中文乱码）
    raw = path.read_text(encoding="utf-8")
    
    # 【高级技巧：保护示例代码区】
    # 提示词里经常会包含大模型的 JSON 输出示例，里面有很多大括号 {}。
    # 如果直接用 Python 的 format() 函数，它会把 JSON 里的 {} 当成变量替换符，从而疯狂报错（KeyError）。
    # 所以这里的逻辑是：我们约定在提示词中，用 "---" 作为分割线。
    # 分割线上半部分是【正文】（需要变量替换），下半部分是【Few-shot 示例】（不需要变量替换）。
    if "---" in raw:
        # 以 "---" 为刀切开文本，取第 0 部分（也就是上半部分正文），并去掉首尾多余空格
        main_part = raw.split("---")[0].strip()
    else:
        # 如果没有分割线，就直接全部当作正文
        main_part = raw.strip()
        
    # 4. 如果调用这个函数时，传入了 kwargs（比如 remaining=10）
    if kwargs:
        # 就使用 .format() 方法，把 main_part 文本里的大括号 {xxx} 替换成对应的值
        return main_part.format(**kwargs)
        
    # 如果没有传参数，直接原样返回文本
    return main_part