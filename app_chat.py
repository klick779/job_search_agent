# -*- coding: utf-8 -*-
"""
Gradio 聊天界面入口 - app_chat.py
职责：为整个 LangGraph 招聘智能体提供一个人机交互 Web 界面。
"""

import os
import sys

from dotenv import load_dotenv
load_dotenv()

# ==========================================
# 模块 1：终极代理防御机制（资深工程师的修养）
# ==========================================
# 为什么要有这堆代码？
# 1. 我们的 Agent 需要调用外部大模型 API（通常需要科学上网代理 HTTP_PROXY）。
# 2. 但 Gradio 启动的本地 UI 是在 127.0.0.1 上。
# 3. 如果不把本地地址加入 NO_PROXY，Gradio 的前后端通信也会绕道代理服务器，导致网页直接白屏打不开！
_http_proxy = os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")
if _http_proxy:
    os.environ["HTTP_PROXY"] = _http_proxy
    os.environ["HTTPS_PROXY"] = _http_proxy
    os.environ["http_proxy"] = _http_proxy
    os.environ["https_proxy"] = _http_proxy

_no_proxy = os.getenv("NO_PROXY", "")
_no_proxy_list = [x.strip() for x in _no_proxy.split(",") if x.strip()] if _no_proxy else []
# 强行把本地回环地址加入白名单，确保 UI 界面秒开
_no_proxy_list.extend(["127.0.0.1", "localhost", "0.0.0.0", "*.gradio.live"])
os.environ["NO_PROXY"] = ",".join(_no_proxy_list)
os.environ["no_proxy"] = ",".join(_no_proxy_list)

# 确保 Python 能找到 src 目录下的包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gradio as gr
from src.agents.runner import run_pipeline


def _to_message_format(history: list) -> list:
    """
    数据格式清洗器
    Gradio 历史上有两种聊天格式：旧版的列表套列表 [[user, bot]]，和新版的字典 [{"role": "user", "content": "..."}]。
    这个函数是为了做向下兼容，强制把所有历史记录转为最新版的标准字典格式。
    """
    out = []
    for item in history:
        if isinstance(item, dict) and "role" in item and "content" in item:
            out.append(item)
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            out.append({"role": "user", "content": item[0] or ""})
            out.append({"role": "assistant", "content": item[1] if item[1] is not None else ""})
    return out


def chat_turn(message: str, history: list):
    """
    处理用户消息的核心生成器（Generator）。
    使用 yield 的好处是可以让前端界面出现“分步加载”的动画效果，而不是死死卡住。
    """
    history = _to_message_format(history or [])

    # 防御性判断：如果用户发了空消息
    if not (message and message.strip()):
        yield history, ""
        return

    # 把用户说的话追加到聊天记录里，并给机器人预留一个空回复的位置
    history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": ""},
    ]

    # --- 阶段 1：点亮 UI 进度提示 ---
    history[-1]["content"] = "⏳ 正在解析您的意图并规划搜索方案…"
    # 第一次 yield：更新界面显示“正在解析”，并清空用户的输入框（""）
    yield history, ""

    # --- 阶段 2：进度推进 ---
    history[-1]["content"] = history[-1]["content"] + "\n\n🚀 正在调动无头浏览器进行全网深度抓取与大模型评估，此过程可能需要几分钟，请稍候…"
    # 第二次 yield：告诉用户系统正在干重活，安抚等待焦虑
    yield history, ""

    # --- 阶段 3：真正的“黑盒”阻塞运行 ---
    # 【注意】：这行代码会卡住，直到 LangGraph 彻底跑完（抓够 50 个岗位）才会往下走
    csv_path, json_path, summary = run_pipeline(user_input=message, output_dir=".")

    # --- 阶段 4：出结果 ---
    if csv_path or json_path:
        history[-1]["content"] = f"**✨ 执行完毕**\n\n{summary}"
    else:
        history[-1]["content"] = f"**⚠️ 执行异常**\n\n{summary}"
    
    # 最后一次 yield：展示最终成绩单
    yield history, ""


def build_ui():
    """使用 Blocks 拼装前端页面"""
    with gr.Blocks(title="AI 招聘 Agent", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 🤖 智能求职搜索 Agent")
        gr.Markdown("输入您的求职意向（如：「帮我找AI 工程师岗位50条」），Agent 将自动为您全网搜罗并整理为表格。")
        
        # 【核心修复】：必须明确声明 type="messages"，否则旧版 Gradio 会无法解析你上面返回的字典格式，导致聊天框白屏！
        chatbot = gr.Chatbot(label="Agent 工作流面板", height=500, type="messages")
        
        with gr.Row():
            msg = gr.Textbox(
                label="发送指令",
                placeholder="在此输入您的搜索需求，按回车发送…",
                scale=7,
            )
            submit_btn = gr.Button("🚀 发送指令", variant="primary", scale=1)
        
        clear_btn = gr.Button("🗑️ 清空工作空间", variant="secondary")

        # 绑定事件处理函数
        def respond(user_msg, history):
            for h, clear in chat_turn(user_msg, history or []):
                yield h, clear

        def clear_chat():
            return [], ""

        # 按回车键发送
        msg.submit(respond, [msg, chatbot], [chatbot, msg])
        # 点击按钮发送
        submit_btn.click(respond, [msg, chatbot], [chatbot, msg])
        # 点击清空
        clear_btn.click(clear_chat, outputs=[chatbot, msg])
        
    return demo


if __name__ == "__main__":
    demo = build_ui()
    # 启动本地服务器。关闭 share=False 防止企业内部代码意外泄露到公网
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False)