# 🏢 AI-Multi-Agent-Interviewer (多智能体 GraphRAG 联合面试系统)

基于 **LangGraph** 多智能体编排与 **Neo4j** 图谱检索（GraphRAG）的端到端全自动 AI 面试流统。

本项目实现了一个从“简历解析”到“多维度拷问”的闭环。上传候选人 PDF 简历后，系统会自动抽取技术栈与项目经历构建三维知识图谱，并由两位性格鲜明的 AI 考官（硬核 Tech Lead + 敏锐 HR 政委）基于图谱动态生成专属面试题，进行交叉火力拷问。

## ✨ 核心亮点 (Features)

* **📄 全自动数据流水线**: 支持一键上传 PDF 简历，底层通过 `Pydantic` 结构化约束大模型输出，全自动构建 Neo4j 图数据库。
* **🕸️ GraphRAG 图谱防伪**: 摒弃传统的向量检索，利用 Cypher 语法从图谱中提取“项目-技术栈”的关联路径，专门针对候选人的交叉技术栈生成底层面试题。
* **🤖 LangGraph 多脑协同**: 采用 StateGraph 状态机架构，Tech Lead 和 HR 交替登场。不仅有对话流转，还具备 `MemorySaver` 断点续传能力（刷新网页不断连）。
* **⚡ 前后端微服务架构**: `FastAPI` 支撑后端核心逻辑与大模型推理，`Streamlit` 提供现代化、流式输出的响应式前端交互。

## 🛠️ 技术栈 (Tech Stack)

* **大模型基座**: 本地部署 Qwen-7B (基于 vLLM 推理加速)
* **多智能体框架**: LangGraph, LangChain
* **图数据库**: Neo4j AuraDB (Cypher)
* **后端 API**: FastAPI, Uvicorn, Pydantic
* **前端交互**: Streamlit

## 🏗️ 系统架构设计

1.  **摄入层 (Ingestion)**: 接收 PDF -> PyPDFLoader 提取文本 -> 大模型结构化解析。
2.  **存储层 (Storage)**: 自动生成 Cypher 语句，将节点 (Person, Project, Skill) 和关系 (PARTICIPATED_IN, USES_TECHNOLOGY) 写入 Neo4j。
3.  **大脑层 (Agent Core)**: 
    * Router 节点负责根据会话状态分配发言权。
    * Tech_Lead 节点负责检索图谱，深挖底层技术原理。
    * HR 节点负责检索专业背景，考察业务思考与跨界动机。
4.  **交互层 (UI)**: Streamlit 提供可视化面板，支持会话记忆 (Thread ID)。

## 🚀 快速启动

### 1. 启动后端 (API 服务)
```bash
uvicorn backend:app --host 0.0.0.0 --port 8080

### 2. 启动前端
streamlit run frontend.py --server.port 6006