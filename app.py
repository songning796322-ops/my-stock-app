import streamlit as st
import requests
import json
import os
import re
import time

# --- 1. 配置中心 (Config) ---
# 你的 API Key
API_KEY = "AIzaSyDoAiYxQjfqgm9ZHBv1mWpfvh7lUB9oARg"

# 你的代理端口 (7897)
PROXY_URL = "http://127.0.0.1:7897"
PROXIES = {
    "http": PROXY_URL,
    "https": PROXY_URL
}

# 目标模型 URL (直接指定，不靠库去猜)
# 我们先试 gemini-1.5-flash，这是目前最通用的
MODEL_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

# --- 2. 页面与样式 (保持 iOS 风格) ---
st.set_page_config(page_title="PolyU MindSpace", page_icon="🧠", layout="centered", initial_sidebar_state="expanded")

st.markdown("""
<style>
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        background-color: #000000 !important;
        color: #E0E0E0;
    }
    footer {visibility: hidden;}
    .stDeployButton {display:none;}

    /* 聊天气泡 */
    .stChatMessage {background-color: transparent !important; border: none !important; padding: 1rem 0;}
    div[data-testid="stChatMessage"]:nth-child(odd) div[data-testid="stMarkdownContainer"] {
        background-color: #FFFFFF !important; color: #000000 !important;
        border-radius: 20px 20px 0px 20px; padding: 12px 18px; float: right;
    }
    div[data-testid="stChatMessage"]:nth-child(odd) div[data-testid="stChatMessageAvatarBackground"] {display: none;}
    div[data-testid="stChatMessage"]:nth-child(even) div[data-testid="stMarkdownContainer"] {
        background-color: #1C1C1E !important; color: #FFFFFF !important;
        border-radius: 20px 20px 20px 0px; padding: 12px 18px; border: 1px solid #333;
    }
    .stTextInput > div > div > input {
        background-color: #1C1C1E !important; color: white !important;
        border-radius: 25px !important; border: 1px solid #333 !important;
    }
    section[data-testid="stSidebar"] {background-color: #121212 !important; border-right: 1px solid #333;}
</style>
""", unsafe_allow_html=True)


# --- 3. 辅助函数 ---
def check_safety(text):
    danger_patterns = [r"(自杀|suicide|kill myself|want to die|不想活了|去死|跳楼|割腕)", r"(绝望|hopeless|无路可走)"]
    return True if re.search("|".join(danger_patterns), text, re.IGNORECASE) else False


def get_crisis_card():
    return """
    <div style="background-color: #1C1C1E; border: 1px solid #FF453A; border-radius: 16px; padding: 20px; margin: 20px 0;">
        <div style="color: #FF453A; font-weight: bold; font-size: 18px;">⚠️ 紧急支援 / Immediate Support</div>
        <div style="font-size:24px; font-weight: 600; margin: 10px 0; color: #FFFFFF;">(852) 2766 5433</div>
    </div>
    """


# PolyU System Prompt
SYSTEM_PROMPT = {
    "role": "user",
    "parts": [{"text": """
    System Instruction: You are "PolyU MindSpace", a warm peer counselor for HK PolyU students. 
    Know about locations (Lib, VA, Z Core) and stressors (GPA, FYP).
    """}]
}
SYSTEM_ACK = {"role": "model", "parts": [{"text": "Understood. I am ready to help."}]}

# --- 4. 侧边栏 ---
with st.sidebar:
    st.title("MindSpace Native")
    st.caption("Mode: Raw HTTP (No SDK)")
    if st.button("🗑️ Reset Chat"):
        st.session_state.messages = []
        st.rerun()

# --- 5. 主逻辑 ---
st.markdown("<h1 style='text-align: center; font-weight: 300;'>MindSpace</h1>", unsafe_allow_html=True)

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "model", "content": "Hey there. How's life at PolyU treating you?"}]

# 显示历史
for msg in st.session_state.messages:
    role = "assistant" if msg["role"] == "model" else "user"
    with st.chat_message(role):
        if msg.get("is_crisis"):
            st.markdown(msg["content"], unsafe_allow_html=True)
        else:
            st.markdown(msg["content"])

# 输入处理
if prompt := st.chat_input("Type here..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    if check_safety(prompt):
        crisis_html = get_crisis_card()
        st.session_state.messages.append({"role": "model", "content": crisis_html, "is_crisis": True})
        with st.chat_message("assistant"):
            st.markdown(crisis_html, unsafe_allow_html=True)
    else:
        # --- 🔥 核心部分：纯手写 HTTP 请求 ---
        with st.chat_message("assistant"):
            placeholder = st.empty()
            placeholder.markdown("Thinking...")

            try:
                # 1. 构建符合 Google API 要求的 JSON
                contents = [SYSTEM_PROMPT, SYSTEM_ACK]
                for m in st.session_state.messages:
                    if not m.get("is_crisis"):
                        contents.append({
                            "role": m["role"],
                            "parts": [{"text": m["content"]}]
                        })

                payload = {
                    "contents": contents,
                    "generationConfig": {"temperature": 0.7}
                }

                # 2. 发送请求 (指定 proxies)
                # 这里的 timeout=30 防止死等
                response = requests.post(
                    MODEL_URL,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    #proxies=PROXIES,
                    timeout=30
                )

                # 3. 处理响应
                if response.status_code == 200:
                    result = response.json()
                    # 提取文本
                    try:
                        full_text = result['candidates'][0]['content']['parts'][0]['text']

                        # 模拟打字机
                        display_text = ""
                        for char in full_text:
                            display_text += char
                            if len(display_text) % 3 == 0:  # 每3个字刷新一次，性能更好
                                placeholder.markdown(display_text + "▌")
                                time.sleep(0.005)
                        placeholder.markdown(full_text)
                        st.session_state.messages.append({"role": "model", "content": full_text})

                    except KeyError:
                        st.error("API 返回了空内容，可能是被安全拦截。")
                        st.json(result)  # 打印出来看看
                else:
                    # 如果出错，直接把 Google 骂回来的话显示出来
                    st.error(f"Google 拒绝了请求 (Status {response.status_code})")
                    st.code(response.text)

            except Exception as e:
                st.error(f"网络连接失败: {str(e)}")