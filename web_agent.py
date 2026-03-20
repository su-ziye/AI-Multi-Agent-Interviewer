import streamlit as st
from neo4j import GraphDatabase
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

# ==========================================
# 1. 基础配置
# ==========================================
NEO4J_URI = "neo4j+s://e9a33f6c.databases.neo4j.io" 
NEO4J_USER = "e9a33f6c"
NEO4J_PASSWORD = "your_password_here"

# ==========================================
# 2. 图谱检索 (加入缓存机制，避免每次刷新网页都去查数据库)
# ==========================================
@st.cache_data
def fetch_interview_context():
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        query = """
        MATCH (p:Person {name: '邱宗彤'})-[:PARTICIPATED_IN]->(pr:Project)-[:USES_TECHNOLOGY]->(sk:Skill)
        RETURN pr.name AS project, collect(sk.name) AS skills, pr.description AS desc
        """
        with driver.session() as session:
            result = session.run(query)
            context = ""
            for record in result:
                context += f"【项目】: {record['project']}\n"
                context += f"【简介】: {record['desc']}\n"
                context += f"【核心技术栈】: {', '.join(record['skills'])}\n"
        driver.close()
        return context
    except Exception as e:
        return f"图谱连接失败: {e}"

# ==========================================
# 3. 页面 UI 设置
# ==========================================
st.set_page_config(page_title="AI 面试官 - Tech Lead", page_icon="🤖", layout="centered")
st.title("🤖 AI-Interviewer: 终极硬核技术面")
st.markdown("---")

# ==========================================
# 4. 初始化会话记忆 (Session State)
# ==========================================
# 只有在第一次加载时，才初始化 LLM 和 聊天历史
if "llm" not in st.session_state:
    # 开启 streaming=True，实现打字机效果
    st.session_state.llm = ChatOpenAI(
        model="qwen-local", 
        api_key="sk-anything", 
        base_url="http://localhost:8000/v1",
        temperature=0.7,
        streaming=True 
    )

if "messages" not in st.session_state:
    # 抓取图谱底细
    graph_context = fetch_interview_context()
    
    # 构建严厉的系统人设
    system_prompt = f"""你是一位极其资深、严格的大厂 AI 算法总监 (Tech Lead)。
现在你面前有一位求职者，这是我从他的简历图谱中提取的底细：
{graph_context}

【你的任务】：
1. 结合他的图谱信息，进行硬核的技术连环追问。
2. 每次只问一个问题，根据他的回答继续深挖，直到探到底层原理（比如 RAG、LoRA、FP16的细节）。
3. 语气要专业、严厉、不留情面。如果在回答中发现漏洞，直接指出来。
4. 第一句话请直接抛出你的第一个针对性问题。"""
    
    st.session_state.messages = [
        SystemMessage(content=system_prompt)
    ]
    st.session_state.chat_history_ui = [] # 专门用于前端展示的列表

# ==========================================
# 5. 渲染聊天界面
# ==========================================
# 展示历史消息
for msg in st.session_state.chat_history_ui:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ==========================================
# 6. 处理用户输入与大模型流式响应
# ==========================================
if user_input := st.chat_input("在此输入你的回答，或者输入 '你好' 开始面试..."):
    # 1. 把用户的话显示在界面上
    with st.chat_message("user"):
        st.markdown(user_input)
    
    # 2. 把用户的话存入记忆数组
    st.session_state.messages.append(HumanMessage(content=user_input))
    st.session_state.chat_history_ui.append({"role": "user", "content": user_input})
    
    # 3. 召唤 Tech Lead 进行流式回复
    with st.chat_message("assistant"):
        # 用 st.write_stream 接收模型的流式输出
        response_stream = st.session_state.llm.stream(st.session_state.messages)
        full_response = st.write_stream(response_stream)
        
    # 4. 把考官的回复存入记忆数组
    st.session_state.messages.append(AIMessage(content=full_response))
    st.session_state.chat_history_ui.append({"role": "assistant", "content": full_response})