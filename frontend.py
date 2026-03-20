import streamlit as st
import requests
import uuid

# ==========================================
# 1. 后端 API 地址配置
# ==========================================
BASE_URL = "http://localhost:8080"
CHAT_API = f"{BASE_URL}/chat"
HISTORY_API = f"{BASE_URL}/history"
UPLOAD_API = f"{BASE_URL}/upload_resume"

st.set_page_config(page_title="AI 面试系统", page_icon="🏢", layout="wide")

# ==========================================
# 2. 状态初始化与断点续传
# ==========================================
if "thread_id" in st.query_params:
    current_thread_id = st.query_params["thread_id"]
else:
    current_thread_id = str(uuid.uuid4())
    st.query_params["thread_id"] = current_thread_id

if "thread_id" not in st.session_state or st.session_state.thread_id != current_thread_id:
    st.session_state.thread_id = current_thread_id
    try:
        resp = requests.get(f"{HISTORY_API}/{current_thread_id}")
        st.session_state.messages = resp.json().get("messages", []) if resp.status_code == 200 else []
    except Exception:
        st.session_state.messages = []

# ==========================================
# 3. 侧边栏：【新增全自动上传组件】
# ==========================================
with st.sidebar:
    st.header("📥 第一步：录入候选人")
    uploaded_file = st.file_uploader("上传简历 (PDF格式)", type=["pdf"])
    
    if uploaded_file and st.button("🚀 AI 自动解析并建档"):
        with st.spinner("🧠 正在呼叫本地大模型阅读简历并构建三维知识图谱..."):
            try:
                files = {"file": (uploaded_file.name, uploaded_file, "application/pdf")}
                upload_resp = requests.post(UPLOAD_API, files=files).json()
                if "candidate_name" in upload_resp:
                    st.success(f"✅ 【{upload_resp['candidate_name']}】 已成功存入 Neo4j 图数据库！")
                    # 自动把输入框的名字替换成刚刚解析出来的名字
                    st.session_state.auto_name = upload_resp['candidate_name']
                else:
                    st.error("❌ 解析失败，请重试。")
            except Exception as e:
                st.error(f"⚠️ 后端连接失败: {e}")
                
    st.markdown("---")
    st.header("⚙️ 第二步：开始面试")
    default_name = st.session_state.get("auto_name", "邱宗彤")
    candidate_name = st.text_input("当前面试候选人", value=default_name)
    
    if st.button("🔄 重置当前面试"):
        new_id = str(uuid.uuid4())
        st.query_params["thread_id"] = new_id
        st.session_state.thread_id = new_id
        st.session_state.messages = []
        st.rerun()

st.title(f"🏢 AI 联合面试：{candidate_name}")
st.markdown("---")

# ==========================================
# 4. 渲染记录与聊天发送
# ==========================================
for msg in st.session_state.messages:
    if msg["role"] == "user":
        with st.chat_message("user", avatar="🧑‍💻"): st.write(msg["content"])
    else:
        speaker = msg.get("speaker", "TechLead")
        avatar = "🌸" if speaker == "HR" else "👨‍💻"
        role_name = "HR 政委" if speaker == "HR" else "Tech Lead"
        with st.chat_message("assistant", avatar=avatar):
            st.write(f"**[{role_name}]：** {msg['content']}")

if user_input := st.chat_input("在此输入你的回答..."):
    with st.chat_message("user", avatar="🧑‍💻"): st.write(user_input)
    st.session_state.messages.append({"role": "user", "content": user_input})
    
    payload = {"thread_id": st.session_state.thread_id, "candidate_name": candidate_name, "message": user_input}
    
    with st.spinner("考官正在思考..."):
        try:
            response = requests.post(CHAT_API, json=payload).json()
            if "detail" in response: # 捕获图谱里没这个人的错误
                st.error(response["detail"])
            else:
                speaker, content = response.get("speaker", "System"), response.get("content", "请求出错")
                avatar = "🌸" if speaker == "HR" else "👨‍💻"
                role_name = "HR 政委" if speaker == "HR" else "Tech Lead"
                with st.chat_message("assistant", avatar=avatar):
                    st.write(f"**[{role_name}]：** {content}")
                st.session_state.messages.append({"role": "assistant", "speaker": speaker, "content": content})
        except Exception as e:
            st.error(f"⚠️ 无法连接到后端服务器: {e}")