from neo4j import GraphDatabase
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

# ==========================================
# 1. 基础配置 (连接你的 Neo4j 大脑)
# ==========================================
NEO4J_URI = "neo4j+s://e9a33f6c.databases.neo4j.io" 
NEO4J_USER = "e9a33f6c"
NEO4J_PASSWORD = "your_password_here" # ⚠️ 再次提醒：项目做完记得重置密码保护安全！

# ==========================================
# 2. 从图谱中挖掘面试考点 (Graph Retrieval)
# ==========================================
def fetch_interview_context():
    print("🕸️ 正在潜入图谱数据库，深挖你的技术底细...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    # 【面试加分项：这就是图数据库的魅力，直接顺藤摸瓜找关系】
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

# ==========================================
# 3. 召唤本地大模型考官出题 (LLM Generation)
# ==========================================
def generate_hard_question(context):
    print("🤖 Tech Lead 考官正在酝酿极其刁钻的问题...")
    
    # 依然调用你本地一直开着的那个 vLLM (Qwen-7B)
    llm = ChatOpenAI(
        model="qwen-local", 
        api_key="sk-anything", 
        base_url="http://localhost:8000/v1",
        temperature=0.7, # 💡 面试官需要发散思维，温度适当调高
    )

    prompt = PromptTemplate.from_template(
        """你是一位极其资深、技术功底深厚的大厂 AI 算法总监 (Tech Lead)。
        现在你面前有一位求职者，这是我从他的知识图谱中提取出来的核心项目底细：
        
        {candidate_context}
        
        【你的任务】：
        请结合上述信息，用严厉、专业且挑剔的口吻，向他提出 **1个** 极具深度的底层技术面试题。
        不要问表面概念！必须深挖他用过的两种技术的结合点（比如 RAG 和 LoRA 结合的挑战），或者追问他在小样本/混合精度训练中踩过的坑。
        
        【输出格式】：
        直接输出面试问题，不要有任何多余的寒暄、问候或自我介绍。
        """
    )

    chain = prompt | llm
    
    try:
        response = chain.invoke({"candidate_context": context})
        return response.content
    except Exception as e:
        print(f"❌ 模型请求失败，请检查 vLLM 服务是否还在运行: {e}")
        return None

# ==========================================
# 主运行入口
# ==========================================
if __name__ == "__main__":
    # 1. 图谱检索
    graph_context = fetch_interview_context()
    
    if graph_context:
        print("\n✅ 查找到的图谱背景如下：\n" + graph_context)
        # 2. LLM 思考发问
        question = generate_hard_question(graph_context)
        if question:
            print("\n🔥 【Tech Lead 的夺命拷问】:\n" + question)
    else:
        print("❌ 没有从图谱中找到数据，请确认图谱是否为空！")