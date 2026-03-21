# -*- coding: utf-8 -*-
# 上面这行告诉 Python 解释器，这个文件使用的是 UTF-8 编码，支持中文，防止乱码。

"""
输出格式化工具模块 - src/utils/output_formatter.py
该模块负责将收集到的岗位数据清洗并输出为标准化的 JSON 和 CSV 文件。
作用：将 Agent 输出的原始数据转换为对终端用户友好的格式。
效果：生成 standardized_ai_jobs.csv 和 standardized_ai_jobs.json 两个交付文件。
"""

import json                  # 导入 json 模块，用于处理 JSON 文件的读写
import pandas as pd          # 导入 pandas 数据处理库，并简写为 pd
from typing import List, Dict # 从 typing 模块导入 List 和 Dict，用于代码的类型提示

def deduplicate_jobs(jobs: List[Dict]) -> List[Dict]:
    """
    去重：按 job_url 去重，同 URL 只保留第一条。
    符合作业流程「搜索 → 抓取 → 解析 → 去重 → 存储」中的去重步骤。
    """
    seen = set()             # 创建一个空的集合 (set)，用来记录我们已经见过的 URL。集合的查找速度极快。
    out = []                 # 创建一个空列表，用来存放最终不重复的岗位数据。
    
    for job in jobs:         # 遍历传入的岗位列表，每次取出一个岗位字典，命名为 job
        # 尝试获取岗位的 URL。用 .get() 的好处是，如果字典里没有这个键，不会报错崩溃，而是返回 None。
        # 这里做了兼容：有些数据可能叫 'job_url'，有些叫 'url'。如果都没有，就给一个空字符串 ""。
        url = job.get("job_url") or job.get("url") or ""
        
        # 将 URL 两端多余的标点符号和空格剥离掉（.strip() 去空格，.rstrip() 去右边的特定字符）
        url = url.strip().rstrip(".,;,: ")
        
        # 将 URL 右边的斜杠 "/" 去掉，并且全部转为小写 (.lower())，作为去重的唯一标识符 (key)
        # 这样做是为了防止 "http://a.com" 和 "HTTP://A.COM/" 被误认为是两个不同的网址
        key = url.rstrip("/").lower() if url else ""
        
        # 如果这个 key 存在（不是空字符串），并且这个 key 还没有出现在 seen 集合中
        if key and key not in seen:
            seen.add(key)    # 将这个新的 key 加入“已见”集合中
            out.append(job)  # 将这个不重复的岗位加入到输出列表中
            
        # 如果这个岗位根本没有提取到 URL (key 是空的)
        elif not key:
            out.append(job)  # 没有 URL 就不去重了，直接当做有效数据保留下来
            
    return out               # 返回去重后的岗位列表


def format_and_save_jobs(jobs: List[Dict], output_dir: str = ".") -> tuple:
    """
    将岗位数据格式化为标准格式并保存到本地文件。

    参数：
        jobs: 包含岗位信息的字典列表
        output_dir: 输出文件目录，默认为当前目录

    效果：
        1. 将列表形式的 tech_tags 转换为逗号分隔的字符串
        2. 移除内部评估字段 is_valid_role
        3. 生成 CSV 和 JSON 两种格式的文件

    返回：
        (csv_path, json_path) 的元组，便于调用方在聊天等场景中展示路径；
        若无数据则返回 (None, None)。
    """
    # 检查传入的数据是不是空的。如果是空的（例如 Agent 没有搜索到任何结果）
    if not jobs:
        print("没有需要保存的岗位数据。")  # 在控制台打印提示
        return (None, None)            # 返回两个 None，表示没有生成任何文件路径
    # --- 第 1 步：清洗字典中的空值和 URL 格式，并剔除无效数据 ---
    cleaned_jobs = []        # 创建一个空列表，存放最终干净且有效的岗位数据
    for job in jobs:         # 遍历每一个岗位字典
        
        # 1. 过滤掉值为 None 的空字段，缩小数据体积
        cleaned_job = {k: v for k, v in job.items() if v is not None}
        
        # 2. 尝试提取这条数据的 URL（兼容 'job_url' 和 'url' 两种命名）
        # 如果这两个键都没有，或者值是空的，url 变量就会变成空字符串 ""
        url = cleaned_job.get("job_url") or cleaned_job.get("url") or ""
        
        # 3. 清理 URL 格式：去除两端的空格和多余标点
        if isinstance(url, str):
            url = url.strip().rstrip(".,;,: ")
        else:
            url = "" # 如果因为某些异常，抓取到的 URL 不是字符串，强制重置为空
            
        # 4. 【核心修改点】：判断 URL 是否有效
        if not url:
            # 如果 url 是空的，打印一条日志，保留 Agent 出错的“案发现场”方便后续排查
            job_name = cleaned_job.get("job_name", "未知岗位")
            print(f"⚠️ 数据清洗拦截：剔除了一条无 URL 的无效岗位 -> [{job_name}]")
            
            # 使用 continue 关键字！
            # 它的意思是：“跳过当前循环剩下的代码，直接去处理下一个 job”。
            # 这样，这条没有 URL 的垃圾数据就不会被执行到最后的 append()，成功被抛弃。
            continue 
            
        # 5. 如果代码能走到这里，说明这条岗位是有 URL 的
        # 我们把刚才清理干净的完美 url 重新塞回字典里覆盖旧的
        if "job_url" in cleaned_job:
            cleaned_job["job_url"] = url
        else:
            cleaned_job["url"] = url
            
        # 6. 将这颗“好果子”放进我们最终的篮子里
        cleaned_jobs.append(cleaned_job)
    
    # --- 第 2 步：转换为 DataFrame 进行高级清洗 ---
    # 将清洗后的字典列表转换成 pandas 的 DataFrame（可以想象成代码里的虚拟 Excel 表）
    df = pd.DataFrame(cleaned_jobs)
    
    # 检查 DataFrame 的列名中是否包含 'tech_tags'（技术标签列，通常是个列表，如 ["Python", "AI"]）
    if 'tech_tags' in df.columns:
        # 对 'tech_tags' 这一列的每一行 (x) 应用一个匿名函数 (lambda)
        # 如果 x 是一个列表，就用 ", " 把它们拼成一个完整的字符串；如果不是，就保持原样。
        # 作用：CSV 格式不支持嵌套列表，必须转成字符串，否则存入 CSV 会变成难看的 "['Python', 'AI']"
        df['tech_tags'] = df['tech_tags'].apply(
            lambda x: ", ".join(x) if isinstance(x, list) else x
        )
    
    # 检查列名中是否包含 'is_valid_role' 和 'extraction_reasoning'（这些是 Agent 内部推理字段）
    for internal_field in ['is_valid_role', 'extraction_reasoning']:
        if internal_field in df.columns:
            df = df.drop(columns=[internal_field])
    
    # --- 第 3 步：定义输出文件的路径 ---
    # 使用 f-string (格式化字符串) 拼接目录和文件名
    csv_path = f"{output_dir}/Jobs.csv"
    json_path = f"{output_dir}/Jobs.json"
    
    # --- 第 4 步：保存为 CSV 文件 ---
    # index=False 表示不要把每行的行号（0, 1, 2...）存进文件里
    # encoding="utf-8-sig" 是非常核心的一个技巧！加上 -sig (BOM 头)，Windows 下的 Excel 双击打开才不会中文乱码
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")
    
    # --- 第 5 步：保存为 JSON 文件 ---
    final_jobs = []          # 准备一个新的列表存 JSON 数据（因为 JSON 可以保留原来的列表结构，不需要像 CSV 那样转字符串）
    for job in cleaned_jobs: # 遍历第一步清洗出的原始字典（这里的 tech_tags 依然还是列表）
        job_copy = job.copy() # 拷贝一份字典，防止修改原数据
        # 同样需要脱敏，删掉 Agent 内部推理字段
        for internal_field in ['is_valid_role', 'extraction_reasoning']:
            if internal_field in job_copy:
                del job_copy[internal_field]
        final_jobs.append(job_copy) # 将处理好的字典加入最终列表
    
    # 使用上下文管理器 (with open) 打开一个 JSON 文件进行写入 ("w" 代表 write)
    # encoding="utf-8" 保证写入时支持中文
    with open(json_path, "w", encoding="utf-8") as json_file:
        # json.dump 负责把 Python 列表/字典转成 JSON 文本写入文件
        # ensure_ascii=False 确保中文正常显示（而不是变成 \u4e2d 这种 Unicode 码）
        # indent=4 表示生成的 JSON 文件会自动换行并缩进4个空格，方便人类阅读
        json.dump(final_jobs, json_file, ensure_ascii=False, indent=4)

    # 打印成功提示信息
    print(f">>> 已生成：{csv_path} 及 {json_path}")
    
    # 返回生成的两个文件的路径元组，方便在其它代码模块（比如 gradio 界面）中直接调用这两个文件
    return (csv_path, json_path)