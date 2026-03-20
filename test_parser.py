import os
import json
import re 
from langchain_community.document_loaders import PyPDFLoader
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from pydantic import BaseModel, Field, field_validator
from typing import List, Union

# ==========================================
# 1. 数据结构定义 (保持不变)
# ==========================================
class Project(BaseModel):
    project_name: str = Field(
        default="未提及", 
        description="项目名称。通常带有'系统'、'平台'、'项目'字样，或者是具体的英文代号"
    )
    tech_stack: Union[List[str], str] = Field(
        default_factory=list, 
        description="该项目使用到的技术栈。最好是数组形式，如 ['RAG', 'LoRA']"
    )
    description: str = Field(default="未提及", description="项目核心内容与候选人的主要贡献摘要")

    @field_validator('tech_stack', mode='before')
    @classmethod
    def clean_tech_stack(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in re.split(r'[、，,]+', value) if item.strip()]
        return value

class EducationItem(BaseModel):
    school: str = Field(default="未提及", description="学校名称")
    major: str = Field(default="未提及", description="专业")
    degree: str = Field(default="未提及", description="学历 (如本科、硕士)")

class ResumeInfo(BaseModel):
    name: str = Field(
        default="未知", 
        description="候选人真实姓名。通常在简历的最开头、第一行大字，或紧挨着联系电话/邮箱，绝对不能填入'未知'"
    )
    education: List[EducationItem] = Field(default_factory=list, description="候选人的教育背景列表")
    core_skills: List[str] = Field(default_factory=list, description="候选人掌握的核心专业技能")
    projects: List[Project] = Field(default_factory=list, description="候选人的项目经历列表")

# ==========================================
# 2. 读取 PDF 文本 (保持不变)
# ==========================================
def extract_text_from_pdf(pdf_path: str) -> str:
    print(f"📄 正在读取 PDF: {pdf_path}...")
    try:
        loader = PyPDFLoader(pdf_path)
        pages = loader.load()
        return "\n".join([page.page_content for page in pages])
    except Exception as e:
        print(f"❌ 读取 PDF 失败: {e}")
        return ""

# ==========================================
# 3. 核心逻辑：调用【本地】大模型解析
# ==========================================
def parse_resume_with_llm(resume_text: str):
    print("🤖 正在调用本地大模型进行结构化分析...")
    
    # 【核心修改区：将视线从云端切换到本地算力】
    llm = ChatOpenAI(
        model="qwen-local",             # 必须和刚才 vLLM 启动时的 --served-model-name 保持完全一致
        api_key="sk-anything",          # 本地部署不需要真实密钥，随便填个假字符串骗过 LangChain 即可
        base_url="http://localhost:8000/v1", # 指向你刚刚拉起的本地 vLLM 服务地址
        temperature=0.0,                # 依然保持 0.0，追求极致稳定
    )

    structured_llm = llm.with_structured_output(ResumeInfo)

    prompt = PromptTemplate.from_template(
        """你是一个极其严谨的顶级 HR 简历解析专家。
        你的任务是从以下非结构化的简历文本中，精准提取出候选人的核心信息。
        
        【生死攸关的提取纪律】：
        1. 必须严格遵循预设的 JSON Schema 格式输出。
        2. 仔细寻找候选人【姓名】（如邱宗彤等），通常在文本最前方，严禁遗漏！
        3. 仔细寻找【项目名称】，即使它和描述混在一起，也要把它剥离出来。
        4. 保证 core_skills 和 projects 的完整性。
        
        【简历文本】：
        {resume_text}
        """
    )

    chain = prompt | structured_llm

    try:
        result = chain.invoke({"resume_text": resume_text})
        return result
    except Exception as e:
        print(f"❌ 模型解析失败: {e}")
        return None

# ==========================================
# 主运行入口
# ==========================================
if __name__ == "__main__":
    pdf_file_path = "sample_resume.pdf" 
    
    if not os.path.exists(pdf_file_path):
        print(f"请先在当前目录下准备一个 {pdf_file_path} 文件进行测试！")
    else:
        text = extract_text_from_pdf(pdf_file_path)
        if text:
            parsed_data = parse_resume_with_llm(text)
            if parsed_data:
                print("\n✅ 解析成功！输出结构化数据如下：")
                print(json.dumps(parsed_data.model_dump(), indent=4, ensure_ascii=False))