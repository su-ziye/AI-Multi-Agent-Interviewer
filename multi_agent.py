from typing import Annotated, Literal
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from neo4j import GraphDatabase

# ==========================================
# 1. 基础配置与图谱检索 (复用之前的逻辑)
# ==========================================
NEO4J_URI = "neo4j+s://e9a33f6c.databases.neo4j.io" 
NEO4J_USER = "e9a33f6c"
NEO4J_PASSWORD = "your_password_here"


def fetch_interview_context():
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        query = """
        MATCH (p:Person {name: '邱宗彤'})-[:PARTICIPATED_IN]->(pr:Project)-[:USES_TECHNOLOGY]->(sk:Skill)
        RETURN pr.name AS project, collect(sk.name) AS skills, pr.description AS desc
        """
        with driver.session() as session:
            result = session.run(query)
            context = "".join([f"项目:{r['project']} | 技术:{', '.join(r['skills'])}\n" for r in result])
        driver.close()
        return context
    except Exception:
        return "查无此人"

graph_context = fetch_interview_context()

# ==========================================
# 2. 定义大模型基座
# ==========================================
llm = ChatOpenAI(
    model="qwen-local", 
    api_key="sk-anything", 
    base_url="http://localhost:8000/v1",
    temperature=0.7,
)

# ==========================================
# 3. 定义全局状态 (State)
# ==========================================
class InterviewState(TypedDict):
    # messages 会自动把新消息追加到列表末尾
    messages: Annotated[list, add_messages]

# ==========================================
# 4. 定义智能体节点 (Nodes)
# ==========================================
def tech_lead_node(state: InterviewState):
    print("\n[Tech Lead 正在思考...]")
    system_prompt = f"""你是一个严厉的大厂 AI 算法总监。
    这是候选人的图谱底细：{graph_context}
    请根据当前的聊天历史，向他提出一个极其硬核的底层技术问题（如 RAG、LoRA、微调细节）。
    每次只问一个问题，不要废话，不要寒暄。"""
    
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}

def hr_node(state: InterviewState):
    print("\n[HR 政委正在思考...]")
    system_prompt = """你是一个洞察力极强的大厂 HR 政委。
    候选人具备极强的地球物理与地理信息科学的理科背景，目前正在向大模型算法和 Agent 开发方向冲刺。
    请根据聊天历史，从以下角度向他发问：
    1. 跨界转型的核心动机与学习能力验证。
    2. 地球物理/GIS 的空间思维背景，对开发 AI 智能体有什么降维打击的优势？
    语气要温和但带着极强的审视感。每次只问一个问题。"""
    
    messages = [SystemMessage(content=system_prompt)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}

# ==========================================
# 5. 定义路由逻辑 (Conditional Edge)
# ==========================================
def router(state: InterviewState) -> Literal["tech_lead", "hr_expert"]:
    # 核心面试流转逻辑：
    # 统计 AI 考官一共发过几次言。偶数次归技术面，奇数次归 HR 面 (交叉火力)
    ai_msg_count = sum(1 for msg in state["messages"] if isinstance(msg, AIMessage))
    if ai_msg_count % 2 == 0:
        return "tech_lead"
    else:
        return "hr_expert"

# ==========================================
# 6. 编译 LangGraph 工作流
# ==========================================
builder = StateGraph(InterviewState)

# 添加节点
builder.add_node("tech_lead", tech_lead_node)
builder.add_node("hr_expert", hr_node)

# 定义起点：新消息进来后，先经过 router 决定去哪个节点
builder.add_conditional_edges(START, router)

# 定义终点：考官发问完毕后，本次图流转结束，等待用户下一次输入
builder.add_edge("tech_lead", END)
builder.add_edge("hr_expert", END)

# 编译成可运行的 Agent 网络
interview_graph = builder.compile()

# ==========================================
# 主运行入口：终端交互循环
# ==========================================
if __name__ == "__main__":
    print("===========================================")
    print("🎓 多智能体交叉面试系统已启动！")
    print("===========================================")
    
    # 初始化状态
    current_state = {"messages": []}
    
    # 开启对战循环
    while True:
        user_input = input("\n🧑‍💻 你 (输入 'quit' 退出): ")
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("面试结束，感谢你的参与！")
            break
            
        # 将你的话加入状态
        current_state["messages"].append(HumanMessage(content=user_input))
        
        # 将状态喂给图网络，触发 Agent 流转
        result = interview_graph.invoke(current_state)
        
        # 提取最新输出的一句话并打印
        latest_ai_msg = result["messages"][-1]
        
        # 判断是哪个考官说的（通过简单的奇偶逻辑判定 UI）
        ai_count = sum(1 for m in result["messages"] if isinstance(m, AIMessage))
        if ai_count % 2 != 0:
            print(f"\n🔥 [Tech Lead]: {latest_ai_msg.content}")
        else:
            print(f"\n🌸 [HR 政委]: {latest_ai_msg.content}")
        
        # 更新本地状态
        current_state = result