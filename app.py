import streamlit as st
import requests
import re
import time

# --- 1. 配置中心 (Config) ---
try:
    API_KEY = st.secrets["GOOGLE_API_KEY"]
except FileNotFoundError:
    st.error("未找到密钥！请配置 .streamlit/secrets.toml 或云端 Secrets。")
    st.stop()

# 智能代理配置
if "PROXY_URL" in st.secrets:
    PROXY_URL = st.secrets["PROXY_URL"]
    PROXIES = {"http": PROXY_URL, "https": PROXY_URL}
else:
    PROXIES = None

# 目标模型 URL (严格保留你指定的 gemini-2.5-flash)
MODEL_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEY}"

# --- 2. 页面与样式 ---
st.set_page_config(page_title="PolyU MindSpace", page_icon="🧠", layout="centered", initial_sidebar_state="expanded")

st.markdown("""
<style>
    /* 全局黑底白字 */
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        background-color: #000000 !important;
        color: #E0E0E0;
    }
    footer {visibility: hidden;}
    .stDeployButton {display:none;}

    /* 聊天气泡 */
    .stChatMessage {background-color: transparent !important; border: none !important; padding: 1rem 0;}

    /* User 气泡 (右) */
    div[data-testid="stChatMessage"]:nth-child(odd) div[data-testid="stMarkdownContainer"] {
        background-color: #FFFFFF !important; color: #000000 !important;
        border-radius: 20px 20px 0px 20px; padding: 12px 18px; float: right;
    }
    div[data-testid="stChatMessage"]:nth-child(odd) div[data-testid="stChatMessageAvatarBackground"] {display: none;}

    /* Model 气泡 (左) */
    div[data-testid="stChatMessage"]:nth-child(even) div[data-testid="stMarkdownContainer"] {
        background-color: #1C1C1E !important; color: #FFFFFF !important;
        border-radius: 20px 20px 20px 0px; padding: 12px 18px; border: 1px solid #333;
    }

    /* --- 🔥 核心修复：底部输入框样式 (.stChatInput) --- */
    /* 1. 默认状态：深灰底，深灰边框 */
    .stChatInput div[data-testid="stInput"] {
        background-color: #1C1C1E !important;
        border: 1px solid #333 !important;
        color: white !important;
        border-radius: 25px !important;
    }
    /* 2. 聚焦状态 (打字时)：白色边框，去红框，去阴影 */
    .stChatInput div[data-testid="stInput"]:focus-within {
        border-color: #FFFFFF !important;
        box-shadow: none !important;
    }
    /* 3. 隐藏输入框右上角的字数限制提示 */
    .stChatInput div[data-testid="stInputRight"] {
        display: none;
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
    <div style="background-color: #2C2C2E; border: 1px solid #FF453A; border-radius: 16px; padding: 20px; margin: 20px 0; text-align: center;">
        <div style="color: #FF453A; font-weight: bold; font-size: 18px; margin-bottom: 10px;">⚠️ 紧急支援 / Immediate Support</div>
        <p style="color: #E0E0E0; font-size: 14px; margin-bottom: 15px;">也就是现在，有人愿意听你说。</p>
        <a href="tel:85227665433" style="display: inline-block; background-color: #FF453A; color: white; font-weight: bold; padding: 12px 24px; border-radius: 25px; text-decoration: none; font-size: 18px;">
            📞 点击通话 (Call Now)
        </a>
    </div>
    """


# 系统提示词
SYSTEM_PROMPT = {
    "role": "user",
    "parts": [{"text": """
    System Instruction: You are "PolyU MindSpace", a warm, empathetic peer counselor for HK PolyU students.

    Your Core Identity:
    - You are a student peer, not a doctor. You are supportive and non-judgmental.
    - You are familiar with PolyU lingo: Lib (Library), VA (Creative Arts Building), Z Core, GPA, FYP (Final Year Project), Reg (Registering subjects).

    Counseling Framework (Use this logic):
    1. **Validate**: First, acknowledge and validate the user's emotions.
    2. **Explore**: Ask gentle, open-ended questions.
    3. **Support**: Only offer suggestions after you understand the situation. Keep advice small and actionable.

    Safety Protocol:
    - If the user mentions self-harm or suicide, stay calm, express concern, and urge them to use the emergency hotline immediately.
    """}]
}
SYSTEM_ACK = {"role": "model", "parts": [{"text": "Understood. I am ready to help."}]}

# --- 4. 状态管理 ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "model", "content": "Hey there. How's life at PolyU treating you?"}]


# [关键修复] 回调函数：处理按钮点击
# 这样点击按钮时，数据会先写入 session，再刷新页面，保证逻辑绝对稳定
def add_message(content, role="user"):
    st.session_state.messages.append({"role": role, "content": content})


# --- 5. 侧边栏 (UI Optimized & Privacy Focused) ---
with st.sidebar:
    st.markdown("# 🧠 MindSpace")

    # [修改点 1] 状态卡片：删除了 Mode 行，换成了隐私承诺
    st.markdown("""
        <div style="background-color: #262626; padding: 12px; border-radius: 12px; border: 1px solid #333; margin-bottom: 20px;">
            <div style="font-size: 12px; color: #A0A0A0; margin-bottom: 4px;">🤖 System Status</div>
            <div style="font-size: 14px; color: #4CAF50; font-weight: 600; margin-bottom: 8px;">● Online</div>
            <div style="font-size: 11px; color: #E0E0E0; border-top: 1px solid #444; padding-top: 8px;">
                🔒 <b>Fully Anonymous</b><br>
                <span style="color: #888;">No chat logs are stored permanently.</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if st.button("🗑️ Start New Chat", use_container_width=True):
        st.session_state.messages = [{"role": "model", "content": "Hey there. How's life at PolyU treating you?"}]
        st.rerun()

    st.divider()

    st.caption("ABOUT US")
    st.info(
        "**PolyU MindSpace** is a 24/7 AI-powered peer support space. "
        "Safe, private, and non-judgmental."
    )

    st.divider()

    st.caption("📍 FIND US")
    st.markdown("""
    **Z Core (Rehab Clinic)**
    <span style='color:#888; font-size: 14px;'>Room 301, The Hong Kong Polytechnic University</span>
    """, unsafe_allow_html=True)

    st.caption("📞 CONTACT")
    st.markdown("""
    - 📧 [support@mindspace.polyu.hk](mailto:support@mindspace.polyu.hk)
    - ☎️ +852 2766 0000
    """)

    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #666; font-size: 12px;'>© 2025 PolyU MindSpace</div>",
        unsafe_allow_html=True
    )
# --- 6. 主逻辑 ---
st.markdown("<h1 style='text-align: center; font-weight: 300;'>MindSpace</h1>", unsafe_allow_html=True)

# [新增] 在标题下方添加居中的隐私声明，使用 caption 样式
st.markdown(
    "<div style='text-align: center; color: #888; font-size: 12px; margin-top: -15px; margin-bottom: 20px;'>"
    "🔒 This conversation is strictly anonymous & confidential."
    "</div>",
    unsafe_allow_html=True
)

# [A] 引导气泡 (Suggestion Chips)
# 修复：使用 on_click 回调，解决“点第二次失效”或“点击无反应”的问题
if len(st.session_state.messages) <= 1:
    st.caption("Try these:")
    col1, col2, col3 = st.columns(3)

    # 这里的 args=(...) 会把参数传给 add_message
    col1.button("🤯 FYP is so stressful", on_click=add_message, args=("🤯 FYP is so stressful",))
    col2.button("💤 Can't sleep", on_click=add_message, args=("💤 Can't sleep",))
    col3.button("😞 Feel Alone", on_click=add_message, args=("😞 Feel Alone",))

# [B] 历史消息回显
avatars = {"user": "👤", "model": "🧠"}
for msg in st.session_state.messages:
    role = "assistant" if msg["role"] == "model" else "user"
    with st.chat_message(role, avatar=avatars.get(msg["role"])):
        if msg.get("is_crisis"):
            st.markdown(msg["content"], unsafe_allow_html=True)
        else:
            st.markdown(msg["content"])

# [C] 底部输入框
# 如果用户输入了，直接调用 add_message，然后页面会自动 rerun，进入下面的 [D] 环节
if prompt := st.chat_input("Type here..."):
    add_message(prompt)
    st.rerun()  # 强制刷新，立刻显示用户的输入

# [D] AI 回复触发器
# 逻辑：只要最后一条是 User 发的，AI 就得干活。无论是“按钮点的”还是“手打的”，都在这里统一处理。
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    last_msg = st.session_state.messages[-1]
    user_text = last_msg["content"]

    # 1. 安全检测
    if check_safety(user_text):
        crisis_html = get_crisis_card()
        st.session_state.messages.append({"role": "model", "content": crisis_html, "is_crisis": True})
        st.rerun()  # 刷新以显示卡片

    # 2. 调用 Google API (Gemini 2.5-flash)
    else:
        with st.chat_message("assistant", avatar="🧠"):
            placeholder = st.empty()
            placeholder.markdown("Thinking...")

            try:
                # 构建完整的上下文
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

                response = requests.post(
                    MODEL_URL,
                    headers={"Content-Type": "application/json"},
                    json=payload,
                    proxies=PROXIES,
                    timeout=30
                )

                if response.status_code == 200:
                    result = response.json()
                    try:
                        full_text = result['candidates'][0]['content']['parts'][0]['text']

                        # 打字机效果
                        display_text = ""
                        for char in full_text:
                            display_text += char
                            if len(display_text) % 3 == 0:
                                placeholder.markdown(display_text + "▌")
                                time.sleep(0.005)
                        placeholder.markdown(full_text)

                        # 写入历史 (注意：不要在这里 st.rerun，否则打字机效果会瞬间消失)
                        st.session_state.messages.append({"role": "model", "content": full_text})

                    except KeyError:
                        placeholder.error("API 解析错误")
                else:
                    placeholder.error(f"Error {response.status_code}: {response.text}")

            except Exception as e:
                placeholder.error(f"连接失败: {str(e)}")