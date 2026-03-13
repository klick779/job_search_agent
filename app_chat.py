# -*- coding: utf-8 -*-
"""
Gradio 聊天界面入口 - app_chat.py
为求职搜索系统提供 Web 聊天入口
"""

import os
import sys

from dotenv import load_dotenv
load_dotenv()

_http_proxy = os.getenv("HTTP_PROXY") or os.getenv("HTTPS_PROXY")
if _http_proxy:
    os.environ["HTTP_PROXY"] = _http_proxy
    os.environ["HTTPS_PROXY"] = _http_proxy
    os.environ["http_proxy"] = _http_proxy
    os.environ["https_proxy"] = _http_proxy

_no_proxy = os.getenv("NO_PROXY", "")
_no_proxy_list = [x.strip() for x in _no_proxy.split(",") if x.strip()] if _no_proxy else []
_no_proxy_list.extend(["127.0.0.1", "localhost", "0.0.0.0", "*.gradio.live"])
os.environ["NO_PROXY"] = ",".join(_no_proxy_list)
os.environ["no_proxy"] = ",".join(_no_proxy_list)

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import gradio as gr

from src.agents.runner import run_pipeline


def _to_message_format(history: list) -> list:
    """将历史记录转换为 Gradio 要求的 {role, content} 格式"""
    out = []
    for item in history:
        if isinstance(item, dict) and "role" in item and "content" in item:
            out.append(item)
        elif isinstance(item, (list, tuple)) and len(item) >= 2:
            out.append({"role": "user", "content": item[0] or ""})
            out.append({"role": "assistant", "content": item[1] if item[1] is not None else ""})
    return out


def chat_turn(message: str, history: list):
    """处理用户消息：运行 LangGraph 流水线 → 返回结果"""
    history = _to_message_format(history or [])

    if not (message and message.strip()):
        yield history, ""
        return

    history = history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": ""},
    ]

    # 1. 启动 LangGraph 流水线（内部包含意图解析）
    history[-1]["content"] = "正在解析您的意图并规划搜索…"
    yield history, ""

    history[-1]["content"] = history[-1]["content"] + "\n\n正在搜索岗位数据…"
    yield history, ""

    # 2. 运行搜索与抓取流水线
    csv_path, json_path, summary = run_pipeline(user_input=message, output_dir=".")

    # 3. 返回结果
    if csv_path or json_path:
        history[-1]["content"] = f"**执行结果**\n{summary}"
    else:
        history[-1]["content"] = f"**执行结果**\n{summary}"
    yield history, ""


def build_ui():
    """构建 Gradio 聊天界面"""
    with gr.Blocks(title="求职搜索助手", theme=gr.themes.Soft()) as demo:
        gr.Markdown("# 基于 Agent 的求职搜索系统")
        gr.Markdown("在下方输入需求，例如：「我想找xxx岗位xx条」")
        chatbot = gr.Chatbot(label="对话", height=400)
        msg = gr.Textbox(
            label="输入",
            placeholder="输入您的求职搜索需求…",
            scale=7,
        )
        submit_btn = gr.Button("发送", variant="primary", scale=1)
        clear_btn = gr.Button("清空对话", variant="secondary")

        def respond(user_msg, history):
            for h, clear in chat_turn(user_msg, history or []):
                yield h, clear

        def clear_chat():
            return [], ""

        msg.submit(respond, [msg, chatbot], [chatbot, msg])
        submit_btn.click(respond, [msg, chatbot], [chatbot, msg])
        clear_btn.click(clear_chat, outputs=[chatbot, msg])
    return demo


if __name__ == "__main__":
    demo = build_ui()
    demo.launch(server_name="127.0.0.1", server_port=7860, share=False)
