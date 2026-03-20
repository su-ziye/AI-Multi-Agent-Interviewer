import streamlit as st
from typing import Annotated, Literal
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from neo4j import GraphDatabase

# ==========================================
# 1. 基础配置
# ==========================================
NEO4J_URI = "neo4j+s://e9a33f6c.databases.neo4j.io" 
NEO4J_USER = "e9a33f6c"
NEO4J_PASSWORD = "your_password_here"


# ==========================================
# 2. 动态图谱检索 (支持传入任意候选人姓名)
# ==========================================
@st.cache_data
def fetch_interview_context(candidate_name: str):
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        
        # 【优化点1】：用 $name 参数化查询，不再写死名字
        query_projects = """
        MATCH (p:Person {name: $name})-[:PARTICIPATED_IN]->(pr:Project)-[:USES_TECHNOLOGY]->(sk:Skill)
        RETURN pr.name AS project, collect(sk.name) AS skills, pr.description AS desc
        """
        
        query_education = """
        MATCH (p:Person {name: $name})-[:EDUCATED_AT]->(s:School)
        RETURN s.name AS school, labels(s) AS type
        """
        
        with driver.session() as session:
            # 查项目
            proj_result = session.run(query_projects, name=candidate_name)
            context = f"【候选人姓名】: {candidate_name}\n\n"
            context += "【项目经历与技术栈】:\n"
            for r in proj_result:
                context += f"- 项目:{r['project']} | 技术:{', '.join(r['skills'])} | 描述:{r['desc']}\n"
                
            # 查学历 (如果图谱里有的话)
            edu_result = session.run(query_education, name=candidate_name)
            edu_list = [r['school'] for r in edu_result]
            if edu_list:
                context += f"\n【教育背景】: {', '.join(edu_list)}\n"
                
        driver.close()
        
        # 如果什么都没查到
        if "项目:" not in context:
            return None
            
        return context
    except Exception as e:
        return f"图谱连接失败: {e}"

# ==========================================
# 3. 定义大模型基座与状态
# ==========================================
llm = ChatOpenAI(
    model="qwen-local", 
    api_key="sk-anything", 
    base_url="http://localhost:8000/v1",
    temperature=0.7,
)

class InterviewState(TypedDict):
    messages: Annotated[list, add_messages]
    context: str # 将图谱背景存入状态中，让所有 Agent 都能随时读取

# ==========================================
# 4. 优化后的通用提示词 (Nodes)
# ==========================================
def tech_lead_node(state: InterviewState):
    # 【优化点2：Tech Lead 通用提示词】
    system_prompt = f"""你是一个极其严厉、技术功底深厚的大厂 AI 算法总监。
    这是当前候选人的真实简历图谱信息：
    {state["context"]}
    
    【你的任务】：
    请仔细阅读他的图谱信息，找到他项目中使用的**两到三种不同的技术栈**，并针对这些技术的**结合点、底层原理或工程落地痛点**，向他提出一个极其硬核的面试题。
    例如：如果他用了 RAG 和 微调，就问两者的联合优化；如果他用了某种数据库，就问高并发机制。
    
    【要求】：
    每次只抛出一个问题。不要有任何寒暄，直接严厉发问。如果在历史对话中发现他的技术漏洞，请毫不留情地指出并追问。"""
    
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [AIMessage(content=response.content, name="TechLead")]}

def hr_node(state: InterviewState):
    # 【优化点3：HR 通用提示词】
    system_prompt = f"""你是一个洞察力极强、阅人无数的大厂 HR 政委 (HR BP)。
    这是当前候选人的真实简历图谱信息：
    {state["context"]}
    
    【你的任务】：
    请仔细阅读他的专业背景和项目经历。不要问纯技术底层代码！你需要从以下几个通用维度中**挑选一个**进行深度发问：
    1. **跨界/学习能力**：如果他的专业和当前做的项目有反差，请让他解释动机和独特的思维优势。
    2. **项目业务价值**：让他阐述图谱中某个项目的实际业务落地痛点和收益。
    3. **抗压与协同**：结合他项目描述中的难点（如“小样本”、“时间紧”），追问他的心态和方法论。
    
    【要求】：
    语气温和但带着极强的审视感，也就是常说的“笑面虎”。每次只问一个问题。"""
    
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [AIMessage(content=response.content, name="HR")]}

def router(state: InterviewState) -> Literal["tech_lead", "hr_expert"]:
    ai_msg_count = sum(1 for msg in state["messages"] if isinstance(msg, AIMessage))
    if ai_msg_count % 2 == 0:
        return "tech_lead"
    else:
        return "hr_expert"

@st.cache_resource
def build_graph():
    builder = StateGraph(InterviewState)
    builder.add_node("tech_lead", tech_lead_node)
    builder.add_node("hr_expert", hr_node)
    builder.add_conditional_edges(START, router)
    builder.add_edge("tech_lead", END)
    builder.add_edge("hr_expert", END)
    return builder.compile()

interview_graph = build_graph()

# ==========================================
# 5. Streamlit 网页渲染与交互逻辑
# ==========================================
st.set_page_config(page_title="AI 面试系统", page_icon="🏢", layout="wide")

# 【优化点4】：增加侧边栏配置，让系统变成真正的通用 SaaS 工具
with st.sidebar:
    st.header("⚙️ 面试控制台")
    st.markdown("请输入图数据库中已存在的候选人姓名，系统将自动拉取其图谱生成专属面试题。")
    candidate_name = st.text_input("候选人姓名", value="邱宗彤")
    
    if st.button("🔄 重新开始面试"):
        st.session_state.messages = []
        st.session_state.context_loaded = False
        st.rerun()

st.title(f"🏢 AI 联合面试：{candidate_name}")
st.markdown("---")

# 初始化对话记忆和上下文
if "messages" not in st.session_state:
    st.session_state.messages = []
    st.session_state.context_loaded = False

# 尝试拉取当前配置的候选人信息
candidate_context = fetch_interview_context(candidate_name)

if candidate_context is None:
    st.error(f"❌ 在图数据库中未找到名为【{candidate_name}】的节点，请检查图谱数据！")
else:
    # 渲染历史聊天记录
    for msg in st.session_state.messages:
        if isinstance(msg, HumanMessage):
            with st.chat_message("user", avatar="🧑‍💻"):
                st.write(msg.content)
        elif isinstance(msg, AIMessage):
            if msg.name == "HR":
                with st.chat_message("assistant", avatar="🌸"):
                    st.write(f"**[HR 政委]：** {msg.content}")
            else:
                with st.chat_message("assistant", avatar="👨‍💻"):
                    st.write(f"**[Tech Lead]：** {msg.content}")

    # 处理用户输入
    if user_input := st.chat_input("在此输入你的回答，开始迎接交叉火力..."):
        with st.chat_message("user", avatar="🧑‍💻"):
            st.write(user_input)
            
        st.session_state.messages.append(HumanMessage(content=user_input))
        
        with st.spinner("考官正在交换眼神并酝酿问题..."):
            # 将消息和动态生成的候选人背景一起喂给状态机
            result = interview_graph.invoke({
                "messages": st.session_state.messages,
                "context": candidate_context
            })
            new_ai_msg = result["messages"][-1]
            
        st.session_state.messages.append(new_ai_msg)
        
        if new_ai_msg.name == "HR":
            with st.chat_message("assistant", avatar="🌸"):
                st.write(f"**[HR 政委]：** {new_ai_msg.content}")
        else:
            with st.chat_message("assistant", avatar="👨‍💻"):
                st.write(f"**[Tech Lead]：** {new_ai_msg.content}")