import os
import shutil
import re
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel, Field, field_validator
from typing import Annotated, Literal, List, Union
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import PromptTemplate
from langchain_community.document_loaders import PyPDFLoader
from neo4j import GraphDatabase

# ==========================================
# 1. 全局配置
# ==========================================
NEO4J_URI = "neo4j+s://e9a33f6c.databases.neo4j.io" 
NEO4J_USER = "e9a33f6c"
NEO4J_PASSWORD = "your_password_here"

llm = ChatOpenAI(
    model="qwen-local", 
    api_key="sk-anything", 
    base_url="http://localhost:8000/v1",
    temperature=0.7,
)

# 强制结构化输出的 LLM (专用于解析简历，温度设为0保证稳定)
parser_llm = ChatOpenAI(model="qwen-local", api_key="sk-anything", base_url="http://localhost:8000/v1", temperature=0.0)

app = FastAPI(title="AI Interviewer API")

# ==========================================
# 2. Pydantic 数据结构 (解析简历用)
# ==========================================
class Project(BaseModel):
    project_name: str = Field(description="项目名称")
    tech_stack: Union[List[str], str] = Field(default_factory=list, description="技术栈数组")
    description: str = Field(description="项目描述")

    @field_validator('tech_stack', mode='before')
    @classmethod
    def clean_tech_stack(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in re.split(r'[、，,]+', value) if item.strip()]
        return value

class EducationItem(BaseModel):
    school: str = Field(description="学校名称")
    major: str = Field(description="专业")

class ResumeInfo(BaseModel):
    name: str = Field(description="候选人姓名，极度重要，绝不能错")
    education: List[EducationItem] = Field(default_factory=list, description="教育背景")
    projects: List[Project] = Field(default_factory=list, description="项目经历")

# ==========================================
# 3. 核心流水线：写入图数据库
# ==========================================
def auto_build_graph(data: ResumeInfo):
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        # 创建人
        session.run("MERGE (p:Person {name: $name})", name=data.name)
        # 创建学校
        for edu in data.education:
            session.run("""
                MATCH (p:Person {name: $name})
                MERGE (s:School {name: $school})
                MERGE (p)-[:EDUCATED_AT {major: $major}]->(s)
            """, name=data.name, school=edu.school, major=edu.major)
        # 创建项目和技术栈
        for proj in data.projects:
            session.run("""
                MATCH (p:Person {name: $name})
                MERGE (pr:Project {name: $proj_name})
                ON CREATE SET pr.description = $desc
                MERGE (p)-[:PARTICIPATED_IN]->(pr)
            """, name=data.name, proj_name=proj.project_name, desc=proj.description)
            for tech in proj.tech_stack:
                session.run("""
                    MATCH (pr:Project {name: $proj_name})
                    MERGE (sk:Skill {name: $tech_name})
                    MERGE (pr)-[:USES_TECHNOLOGY]->(sk)
                """, proj_name=proj.project_name, tech_name=tech)
    driver.close()

# ==========================================
# 4. 图谱检索与 LangGraph 状态机 (面试用)
# ==========================================
def fetch_interview_context(candidate_name: str):
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        query = """
        MATCH (p:Person {name: $name})-[:PARTICIPATED_IN]->(pr:Project)-[:USES_TECHNOLOGY]->(sk:Skill)
        RETURN pr.name AS project, collect(sk.name) AS skills, pr.description AS desc
        """
        with driver.session() as session:
            result = session.run(query, name=candidate_name)
            context = f"【候选人】: {candidate_name}\n"
            found = False
            for r in result:
                found = True
                context += f"- 项目:{r['project']} | 技术:{', '.join(r['skills'])}\n"
        driver.close()
        return context if found else None
    except Exception:
        return None

class InterviewState(TypedDict):
    messages: Annotated[list, add_messages]
    context: str 

def tech_lead_node(state: InterviewState):
    prompt = f"你是严厉的大厂技术总监。候选人底细：{state['context']}。请针对他的技术栈提出硬核底层问题，每次只问一个。"
    response = llm.invoke([SystemMessage(content=prompt)] + state["messages"])
    return {"messages": [AIMessage(content=response.content, name="TechLead")]}

def hr_node(state: InterviewState):
    prompt = f"你是洞察力极强的HR政委。候选人底细：{state['context']}。请针对他的跨界背景、动机或项目痛点发问。每次只问一个。"
    response = llm.invoke([SystemMessage(content=prompt)] + state["messages"])
    return {"messages": [AIMessage(content=response.content, name="HR")]}

def router(state: InterviewState) -> Literal["tech_lead", "hr_expert"]:
    return "tech_lead" if sum(1 for msg in state["messages"] if isinstance(msg, AIMessage)) % 2 == 0 else "hr_expert"

memory = MemorySaver()
builder = StateGraph(InterviewState)
builder.add_node("tech_lead", tech_lead_node)
builder.add_node("hr_expert", hr_node)
builder.add_conditional_edges(START, router)
builder.add_edge("tech_lead", END)
builder.add_edge("hr_expert", END)
interview_graph = builder.compile(checkpointer=memory)

# ==========================================
# 5. FastAPI 路由接口
# ==========================================
class ChatRequest(BaseModel):
    thread_id: str
    candidate_name: str
    message: str

@app.post("/chat")
def chat_endpoint(req: ChatRequest):
    context = fetch_interview_context(req.candidate_name)
    if not context:
        raise HTTPException(status_code=404, detail="图谱中查无此人")
    config = {"configurable": {"thread_id": req.thread_id}}
    result = interview_graph.invoke({"messages": [HumanMessage(content=req.message)], "context": context}, config=config)
    new_msg = result["messages"][-1]
    return {"speaker": new_msg.name, "content": new_msg.content}

@app.get("/history/{thread_id}")
def get_history(thread_id: str):
    state = interview_graph.get_state({"configurable": {"thread_id": thread_id}})
    if not state or "messages" not in state.values: return {"messages": []}
    history = []
    for msg in state.values["messages"]:
        if isinstance(msg, HumanMessage): history.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage): history.append({"role": "assistant", "speaker": msg.name, "content": msg.content})
    return {"messages": history}

# 【全新震撼接口】：全自动解析上传流水线
@app.post("/upload_resume")
async def upload_resume(file: UploadFile = File(...)):
    # 1. 存临时文件
    temp_file = f"temp_{file.filename}"
    with open(temp_file, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # 2. 读取 PDF
        loader = PyPDFLoader(temp_file)
        text = "\n".join([page.page_content for page in loader.load()])
        
        # 3. 呼叫大模型结构化解析
        structured_llm = parser_llm.with_structured_output(ResumeInfo)
        prompt = PromptTemplate.from_template("你是一个极其严谨的HR专家。请从以下简历中提取信息，必须包含姓名和项目技术栈。\n{text}")
        parsed_data = (prompt | structured_llm).invoke({"text": text})
        
        # 4. 自动写入图谱
        auto_build_graph(parsed_data)
        
        return {"status": "success", "candidate_name": parsed_data.name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_file): os.remove(temp_file) # 阅后即焚