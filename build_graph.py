from neo4j import GraphDatabase
import json

# ==========================================
# 1. 配置你的 Neo4j 数据库连接
# ==========================================
# 替换为你刚刚在 AuraDB 获取的地址和密码
URI = "neo4j+s://e9a33f6c.databases.neo4j.io"  # 修改这里
USERNAME = "e9a33f6c"                           # 通常默认是 neo4j
PASSWORD = "VTiD16jSAJnr5HCFbscu7F5GsSai0g8c1QQggJIDbNA"                      # 修改这里

# ==========================================
# 2. 准备数据：你刚才提取出的完美 JSON
# ==========================================
resume_data = {
    "name": "邱宗彤",
    "education": [
        {"school": "中国地质大学（北京）", "major": "地球物理学", "degree": "硕士"},
        {"school": "应急管理大学", "major": "地理信息科学", "degree": "本科"}
    ],
    "core_skills": [
        "Transformer/BERT/GPT",
        "LoRA/QLoRA微调",
        "FP16混合精度训练",
        "FAISS向量数据库",
        "LangChain",
        "Python科学计算",
        "C++"
    ],
    "projects": [
        {
            "project_name": "基于维基百科科学内容的FAISS语义检索系统",
            "tech_stack": ["RAG", "LoRA", "FP16混合精度", "DeBERTa", "FAISS", "Hugging Face Transformers"],
            "description": "开发一套LLM问答系统，解决小样本问题，使用Qlora微调优化模型。"
        }
    ]
}

# ==========================================
# 3. 核心逻辑：用 Cypher 语言写入图谱
# ==========================================
class KnowledgeGraphBuilder:
    def __init__(self, uri, user, password):
        # 建立与数据库的驱动连接
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def build_resume_graph(self, data):
        with self.driver.session() as session:
            print("🌐 正在连接图数据库，开始构建知识图谱...")
            
            # 第一步：创建候选人主节点 (MERGE 的作用是：如果存在就匹配，不存在才新建，防止重复创建)
            session.run("MERGE (p:Person {name: $name})", name=data["name"])
            
            # 第二步：连接教育背景
            for edu in data["education"]:
                session.run("""
                    MATCH (p:Person {name: $name})
                    MERGE (s:School {name: $school})
                    MERGE (p)-[:EDUCATED_AT {major: $major, degree: $degree}]->(s)
                """, name=data["name"], school=edu["school"], major=edu["major"], degree=edu["degree"])
                
            # 第三步：连接核心技能
            for skill in data["core_skills"]:
                session.run("""
                    MATCH (p:Person {name: $name})
                    MERGE (sk:Skill {name: $skill_name})
                    MERGE (p)-[:HAS_CORE_SKILL]->(sk)
                """, name=data["name"], skill_name=skill)
                
            # 第四步：连接项目与项目使用的技术栈
            for proj in data["projects"]:
                # 建立人与项目的关系
                session.run("""
                    MATCH (p:Person {name: $name})
                    MERGE (pr:Project {name: $proj_name})
                    ON CREATE SET pr.description = $desc
                    MERGE (p)-[:PARTICIPATED_IN]->(pr)
                """, name=data["name"], proj_name=proj["project_name"], desc=proj["description"])
                
                # 建立项目与具体技术栈的交叉关系 (图谱防伪的核心！)
                for tech in proj["tech_stack"]:
                    session.run("""
                        MATCH (pr:Project {name: $proj_name})
                        MERGE (sk:Skill {name: $tech_name})
                        MERGE (pr)-[:USES_TECHNOLOGY]->(sk)
                    """, proj_name=proj["project_name"], tech_name=tech)
                    
            print("✅ 知识图谱构建完成！")

# ==========================================
# 主运行入口
# ==========================================
if __name__ == "__main__":
    builder = KnowledgeGraphBuilder(URI, USERNAME, PASSWORD)
    try:
        builder.build_resume_graph(resume_data)
    finally:
        builder.close()