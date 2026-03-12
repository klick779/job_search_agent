# -*- coding: utf-8 -*-
"""
输出格式化工具模块 - src/utils/output_formatter.py
该模块负责将收集到的岗位数据清洗并输出为标准化的 JSON 和 CSV 文件。
作用：将 Agent 输出的原始数据转换为对终端用户友好的格式。
效果：生成 standardized_ai_jobs.csv 和 standardized_ai_jobs.json 两个交付文件。
"""

import json
import pandas as pd
from typing import List, Dict


def deduplicate_jobs(jobs: List[Dict]) -> List[Dict]:
    """
    去重：按 job_url 去重，同 URL 只保留第一条。
    符合作业流程「搜索 → 抓取 → 解析 → 去重 → 存储」中的去重步骤。
    """
    seen = set()
    out = []
    for job in jobs:
        url = job.get("job_url") or job.get("url") or ""
        url = url.strip().rstrip(".,;,: ")
        key = url.rstrip("/").lower() if url else ""
        if key and key not in seen:
            seen.add(key)
            out.append(job)
        elif not key:
            out.append(job)
    return out


def format_and_save_jobs(jobs: List[Dict], output_dir: str = ".") -> None:
    """
    将岗位数据格式化为标准格式并保存到本地文件。
    参数：
        jobs: 包含岗位信息的字典列表
        output_dir: 输出文件目录，默认为当前目录
    效果：
        1. 将列表形式的 tech_tags 转换为逗号分隔的字符串
        2. 移除内部评估字段 is_valid_ai_role
        3. 生成 CSV 和 JSON 两种格式的文件
    """
    if not jobs:
        print("没有需要保存的岗位数据。")
        return
    
    # 格式化 job_url 
    cleaned_jobs = []
    for job in jobs:
        cleaned_job = {k: v for k, v in job.items() if v is not None}
        for url_key in ("job_url", "url"):
            if url_key in cleaned_job and isinstance(cleaned_job[url_key], str):
                cleaned_job[url_key] = cleaned_job[url_key].rstrip(".,;,: ")
        cleaned_jobs.append(cleaned_job)
    
    # 转换为 DataFrame 进行数据清洗
    df = pd.DataFrame(cleaned_jobs)
    
    # 将 Pydantic 输出的列表形式（tech_tags）处理为逗号分隔的字符串
    # 作用：适应传统的 CSV 结构
    if 'tech_tags' in df.columns:
        df['tech_tags'] = df['tech_tags'].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else x
        )
    
    # 脱敏处理：在最终交付物中移除系统评估时使用的中间布尔变量
    # 作用：保持输出清爽，不暴露内部判断逻辑
    if 'is_valid_ai_role' in df.columns:
        df = df.drop(columns=['is_valid_ai_role'])
    
    # 定义输出文件路径
    csv_path = f"{output_dir}/Jobs.csv"
    json_path = f"{output_dir}/Jobs.json"
    
    # 文件化落盘 (I/O Operations)
    # 使用 utf-8-sig 编码，防止中文 Windows 系统 Excel 打开时出现乱码
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    
    # 同时生成支持后端嵌套解析的纯净 JSON 文件
    # 效果：保留 tech_tags 为数组形式，便于程序读取
    final_jobs = []
    for job in cleaned_jobs:
        job_copy = job.copy()
        if 'is_valid_ai_role' in job_copy:
            del job_copy['is_valid_ai_role']
        final_jobs.append(job_copy)
    
    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(final_jobs, json_file, ensure_ascii=False, indent=4)
    
    print(f">>> 已生成：{csv_path} 及 {json_path}")

