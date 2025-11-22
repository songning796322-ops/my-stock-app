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

# 目标模型 URL
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

    /* 聊天气泡基础设置 */
    .stChatMessage {background-color: transparent !important; border: none !important; padding: 1rem 0;}

    /* User 气泡 (右) */
    div[data-testid="stChatMessage"]:nth-child(even) div[data-testid="stMarkdownContainer"] {
        background-color: #FFFFFF !important; 
        color: #000000 !important;
        border-radius: 20px 20px 0px 20px; 
        padding: 12px 18px; 
        float: right;
    }
    div[data-testid="stChatMessage"]:nth-child(even) div[data-testid="stChatMessageAvatarBackground"] {display: none;}

    /* Model 气泡 (左) */
    div[data-testid="stChatMessage"]:nth-child(odd) div[data-testid="stMarkdownContainer"] {
        background-color: #1C1C1E !important; 
        color: #FFFFFF !important;
        border-radius: 20px 20px 20px 0px; 
        padding: 12px 18px; 
        border: 1px solid #333;
        float: left; 
    }

    /* 底部输入框样式 */
    .stChatInput div[data-testid="stInput"] {
        background-color: #1C1C1E !important;
        border: 1px solid #333 !important;
        color: white !important;
        border-radius: 25px !important;
    }
    .stChatInput div[data-testid="stInput"]:focus-within {
        border-color: #FFFFFF !important;
        box-shadow: none !important;
    }
    .stChatInput div[data-testid="stInputRight"] {
        display: none;
    }

    section[data-testid="stSidebar"] {background-color: #121212 !important; border-right: 1px solid #333;}

    /* --- 侧边栏按钮强力修复 --- */
    section[data-testid="stSidebar"] button {
        background-color: #262626 !important;
        color: #E0E0E0 !important;
        border: 1px solid #333 !important;
        transition: all 0.2s ease !important;
    }
    section[data-testid="stSidebar"] button p,
    section[data-testid="stSidebar"] button div {
        color: #E0E0E0 !important;
    }
    section[data-testid="stSidebar"] button:hover {
        background-color: #333333 !important;
        border-color: #666 !important;
        color: #FFFFFF !important;
    }
    section[data-testid="stSidebar"] button:hover p,
    section[data-testid="stSidebar"] button:hover div {
        color: #FFFFFF !important;
    }
    section[data-testid="stSidebar"] button:active,
    section[data-testid="stSidebar"] button:focus {
        background-color: #444444 !important;
        color: #FFFFFF !important;
        border-color: #FFFFFF !important;
        box-shadow: none !important;
    }
</style>
""", unsafe_allow_html=True)


# --- 3. 辅助函数 ---
def check_safety(text):
    danger_patterns = [r"(自杀|suicide|kill myself|want to die|不想活了|去死|跳楼|割腕)", r"(绝望|hopeless|无路可走)"]
    return True if re.search("|".join(danger_patterns), text, re.IGNORECASE) else False


def get_crisis_card():
    return """
    <div style="background-color: #2C2C2E; border: 1px solid #FF453A; border-radius: 16px; padding: 20px; margin: 20px 0; text-align: center;">
        <div style="color: #FF453A; font-weight: bold; font-size: 30px; margin-bottom: 10px;">Support</div>
        <p style="color: #E0E0E0; font-size: 14px; margin-bottom: 15px;">Whenever you're ready, we are here to listen.</p>
        <a href="tel:85227665433" style="display: inline-block; background-color: #FF453A; color: white; font-weight: bold; padding: 12px 24px; border-radius: 25px; text-decoration: none; font-size: 18px;">
            📞 Call Now
        </a>
    </div>
    """


# 系统提示词
SYSTEM_PROMPT = {
    "role": "user",
    "parts": [{"text": """
    System Instruction: You are "PolyU MindSpace", a warm, empathetic peer counselor.
    Your Core Tasks:
    1. Reply to the user with empathy and support.
    2. **Analyze the user's sentiment** based on their input (-1.0 = suicidal/extreme distress, 0 = neutral, +1.0 = very happy).

    CRITICAL OUTPUT FORMAT:
    You MUST put the sentiment score at the very end of your response in this exact format: [[SCORE:0.5]]
    """}]
}
SYSTEM_ACK = {"role": "model", "parts": [{"text": "Understood. I am ready to help."}]}

# --- 4. 状态管理 ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "model", "content": "Hey there. How's life at PolyU treating you?"}]
if "mood_history" not in st.session_state:
    st.session_state.mood_history = [0.0]


def add_message(content, role="user"):
    st.session_state.messages.append({"role": role, "content": content})


# --- 5. 侧边栏 (UI Optimized & Privacy Focused) ---
with st.sidebar:
    # 标题
    st.markdown("<h1 style='font-size: 36px; margin-bottom: 20px; margin-top: 0;'>MindSpace</h1>",
                unsafe_allow_html=True)

    # 状态卡片
    st.markdown("""
        <div style="background-color: #262626; padding: 12px; border-radius: 12px; border: 1px solid #333; margin-bottom: 20px;">
            <div style="font-size: 12px; color: #A0A0A0; margin-bottom: 4px;">🤖 System Status</div>
            <div style="font-size: 14px; color: #4CAF50; font-weight: 600; margin-bottom: 8px;">● Online Gemini 2.5 Pro</div>
            <div style="font-size: 11px; color: #E0E0E0; border-top: 1px solid #444; padding-top: 8px;">
                🔒 <b>Fully Anonymous</b><br>
                <span style="color: #888;">No chat logs are stored permanently.</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 按钮：清空聊天
    if st.button("Start New Chat", use_container_width=True):
        st.session_state.messages = [{"role": "model", "content": "Hey there. How's life at PolyU treating you?"}]
        st.session_state.mood_history = [0.0]
        st.rerun()

    # 导出功能
    def convert_chat_to_text():
        history_text = "MindSpace Chat History\n=======================\n\n"
        for msg in st.session_state.messages:
            role = "User" if msg["role"] == "user" else "MindSpace"
            content = msg["content"]
            if msg.get("is_crisis"):
                content = "[System Alert: Crisis Support Information Displayed]"
            history_text += f"[{role}]:\n{content}\n\n{'-' * 30}\n\n"
        return history_text

    chat_log = convert_chat_to_text()
    # 按钮：下载
    st.download_button(
        label="Download Chat Log",
        data=chat_log,
        file_name="mindspace_chat_history.txt",
        mime="text/plain",
        use_container_width=True
    )

    st.divider()

    # 情绪仪表盘
    st.markdown("Mood Tracker")
    if st.session_state.mood_history:
        current_score = st.session_state.mood_history[-1]
    else:
        current_score = 0.0

    if current_score >= 0.6:
        mood_emoji = "🤩"
        mood_state = "Excellent"
        score_color = "#2E7D32"
    elif 0.2 <= current_score < 0.6:
        mood_emoji = "🙂"
        mood_state = "Good"
        score_color = "#66BB6A"
    elif -0.2 <= current_score < 0.2:
        mood_emoji = "😐"
        mood_state = "Neutral"
        score_color = "#9E9E9E"
    elif -0.6 <= current_score < -0.2:
        mood_emoji = "🌧️"
        mood_state = "Low"
        score_color = "#FFA726"
    else:
        mood_emoji = "😫"
        mood_state = "Stressed"
        score_color = "#EF5350"

    st.markdown(f"""
        <div style="
            background-color: #1E1E1E; 
            border-radius: 12px; 
            padding: 15px; 
            display: flex; 
            align-items: center; 
            justify-content: space-between; 
            border: 1px solid #333;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        ">
            <div style="font-size: 38px;">{mood_emoji}</div>
            <div style="text-align: right;">
                <div style="color: #888; font-size: 12px; margin-bottom: 4px;">Current Vibe</div>
                <div style="color: {score_color}; font-weight: 700; font-size: 20px;">{mood_state}</div>
                <div style="color: #555; font-size: 10px;">Score: {current_score:.2f}</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    st.divider()

    st.caption("ABOUT US")
    st.markdown("""
    <div style="background-color: #262626; padding: 12px; border-radius: 12px; border: 1px solid #333; font-size: 14px; color: #E0E0E0;">
        <b>PolyU MindSpace</b> is a 24/7 AI-powered peer support space.<br>
        <span style="color: #A0A0A0;">Safe, private, and non-judgmental.</span>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # --- 🟢 [核心修复] 底部信息卡片 (移除了每行HTML前的空格缩进) ---
    st.markdown("""
<div style="background-color: #1E1E1E; border: 1px solid #333; border-radius: 12px; padding: 18px; font-size: 13px; color: #E0E0E0; line-height: 1.5;">
    <div style="margin-bottom: 16px;">
        <div style="color: #666; font-size: 10px; font-weight: 700; letter-spacing: 1px; margin-bottom: 6px; text-transform: uppercase;">Location</div>
        <div style="font-weight: 500; font-size: 14px; margin-bottom: 2px;">Z Core ( Rehab Clinic )</div>
        <div style="color: #999; font-size: 12px;">Room 301, The Hong Kong Polytechnic University</div>
    </div>
    <div style="height: 1px; background-color: #333; margin-bottom: 16px;"></div>
    <div>
        <div style="color: #666; font-size: 10px; font-weight: 700; letter-spacing: 1px; margin-bottom: 6px; text-transform: uppercase;">Contact</div>
        <div style="margin-bottom: 4px;">
            <a href="mailto:support@mindspace.polyu.hk" style="color: #E0E0E0; text-decoration: none; transition: color 0.2s;">support@mindspace.polyu.hk</a>
        </div>
        <div style="color: #E0E0E0;">+852 2766 0000</div>
    </div>
</div>
    """, unsafe_allow_html=True)

    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #666; font-size: 12px;'>© 2025 PolyU MindSpace</div>",
        unsafe_allow_html=True
    )

# --- 6. 主逻辑 ---

st.markdown("##### **MindSpace**")

st.markdown(
    "<h1 style='text-align: center; font-weight: 600; font-size: 2.5rem; margin-top: 10px; margin-bottom: 10px;'>How are you feeling today?</h1>",
    unsafe_allow_html=True
)

st.markdown(
    "<div style='text-align: center; color: #888; font-size: 12px; margin-bottom: 40px;'>"
    "🔒 This conversation is strictly anonymous & confidential."
    "</div>",
    unsafe_allow_html=True
)

# [A] 引导气泡
if len(st.session_state.messages) <= 1:
    c1, c2, c3, c4, c5 = st.columns([1, 2, 2, 2, 1])
    with c2:
        st.button("🤯 So Stressful", on_click=add_message, args=("🤯 FYP is so stressful",), use_container_width=True)
    with c3:
        st.button("💤 Can't sleep", on_click=add_message, args=("💤 Can't sleep",), use_container_width=True)
    with c4:
        st.button("😞 Feel Alone", on_click=add_message, args=("😞 Feel Alone",), use_container_width=True)

# [B] 历史消息
avatars = {"user": "👤", "model": "🧠"}
for msg in st.session_state.messages:
    role = "assistant" if msg["role"] == "model" else "user"
    with st.chat_message(role, avatar=avatars.get(msg["role"])):
        if msg.get("is_crisis"):
            st.markdown(msg["content"], unsafe_allow_html=True)
        else:
            st.markdown(msg["content"])

# [C] 输入框
if prompt := st.chat_input("Type here..."):
    add_message(prompt)
    st.rerun()

# [D] AI 回复逻辑
if st.session_state.messages and st.session_state.messages[-1]["role"] == "user":
    last_msg = st.session_state.messages[-1]
    user_text = last_msg["content"]

    if check_safety(user_text):
        crisis_html = get_crisis_card()
        st.session_state.messages.append({"role": "model", "content": crisis_html, "is_crisis": True})
        st.rerun()
    else:
        with st.chat_message("assistant", avatar="🧠"):
            placeholder = st.empty()
            placeholder.markdown("Thinking...")

            try:
                contents = [SYSTEM_PROMPT, SYSTEM_ACK]
                for m in st.session_state.messages:
                    if not m.get("is_crisis"):
                        contents.append({"role": m["role"], "parts": [{"text": m["content"]}]})

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
                        raw_text = result['candidates'][0]['content']['parts'][0]['text']
                        sentiment_score = 0.0
                        clean_text = raw_text

                        match = re.search(r"\[\[SCORE:\s*([-+]?\d*\.?\d+)\]\]", raw_text)
                        if match:
                            sentiment_score = float(match.group(1))
                            sentiment_score = max(-1.0, min(1.0, sentiment_score))
                            st.session_state.mood_history.append(sentiment_score)
                            clean_text = raw_text.replace(match.group(0), "").strip()
                        else:
                            if st.session_state.mood_history:
                                st.session_state.mood_history.append(st.session_state.mood_history[-1])

                        display_text = ""
                        for char in clean_text:
                            display_text += char
                            if len(display_text) % 3 == 0:
                                placeholder.markdown(display_text + "▌")
                                time.sleep(0.03)
                        placeholder.markdown(clean_text)

                        st.session_state.messages.append({"role": "model", "content": clean_text})

                        if sentiment_score <= -0.9:
                            crisis_html = get_crisis_card()
                            st.session_state.messages.append(
                                {"role": "model", "content": crisis_html, "is_crisis": True})
                            st.toast("⚠️ Crisis Support Information Displayed", icon="🛡️")

                        time.sleep(0.5)
                        st.rerun()

                    except KeyError:
                        placeholder.error("API 解析错误")
                else:
                    placeholder.error(f"Error {response.status_code}: {response.text}")

            except Exception as e:
                placeholder.error(f"连接失败: {str(e)}")