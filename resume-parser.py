import os
from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel
import json

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise ValueError("API Key unavailable.")

client = Groq(api_key=api_key)
model = "openai/gpt-oss-120b"

job_description="""
Associate Applied AI Engineer
Northstar Labs · Pune, India · Hybrid · Full time

Northstar Labs is looking for an Associate Applied AI Engineer to help build tools that turn business documents and text into reliable, structured data. You’ll work with product and engineering teammates to prototype and improve language-model features used in internal and customer-facing workflows.

What you’ll do
- Build Python services that process text and documents such as PDFs and Word files.
- Use hosted language-model APIs to extract, classify, or summarize information.
- Validate model responses with typed schemas and return clean JSON through APIs.
- Create evaluation examples, review errors, and improve prompt and extraction quality.
- Collaborate on testing, documentation, and safe handling of personal or confidential data.
What we’re looking for
- Two or more years of experience with Python software development, data engineering, or applied machine learning.
- Experience with REST APIs, SQL, Git, and automated testing.
- Familiarity with an LLM API, NLP, information extraction, or document-processing tools.
- Experience with Pydantic or another data-validation library is helpful.
- Clear communication and a practical approach to debugging.
Experience deploying services with Docker or a cloud platform is a plus. A degree in computer science, engineering, statistics, or equivalent practical experience is welcome.
"""

class Job(BaseModel):
    role:str
    required_skills:list[str]
    preferred_skille:list[str]
    minimum_experience:float|None
    education_requirements:list[str]
    responsibilities:list[str]
    
jd_schema=Job.model_json_schema()

system_prompt=f"""
You are an expert HR assistant.

Your job is to analyze the job description and extract structured information 
from them.

Return only valid JSON matching this schema: {jd_schema}

IMPORTANT:
Do not return the schema itself.
Do not return unnecessary fields like "properties", "title", "type" etc.
Fill the schema with actual information extracted from the job description.

If minimum experience is not mentioned, return null.
If information for a list is missing, return an empty list.

DO NOT INVENT INFORMATION.
"""
user_prompt=f"""
Analyze the following job description: {job_description}
"""

system_message={"role":"system","content":system_prompt}
user_message={"role":"user","content":user_prompt}
response_format={"type":"json_object"}

messages=[system_message,user_message]

response=client.chat.completions.create(model=model,message=messages,response_format=response_format)

raw_json=response.choice[0].message.content

job_data=json.loads(raw_json)
job=Job(**job_data)

# print(job.minimum_experience)
# print(job.education_requirements)

class MatchResult(BaseModel):
    details:dict

class Experience(BaseModel):
    company:str|None=None
    role:str|None=None
    duration:str|None=None
    description:str|None=None
    skills_used:list[str]=[]
    
class Resume(BaseModel):
    name:str|None=None
    email:str|None=None
    phone= str|None=None
    
    total_experience_years:float|None=None
    
    skills:list[str]=[]
    experience:list[Experience]=[]
    education:list[str]=[]
    projects:list[str]=[]
    certifications:list[str]=[]
    
resume_schema=Resume.model_json_schema()



from pypdf import PdfReader
from docx import Document

def read_pdf(file_path):
    reader=PdfReader(file_path)
    text=""
    for page in reader.pages:
        page_text=page.extract_text()
        if page_text:
            text+=page_text+'\n'
    return text

def read_docx(file_path):
    document=Document(file_path)
    text=""
    for paragraph in document.paragraph:
        if paragraph.text.strip():
            text+=paragraph.text+'\n'
        
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                if cell.text.strip():
                    text+=cell.text+'\n'
    
    return text

def read_resume(file_path):
    if file_path.suffix.lower()==".pdf":
        return read_pdf(file_path)
    elif file_path.suffix.lower()==".docx":
        return read_docx(file_path)
    else:
        return None
    
resume_folder=Path("resumes")
all_result=[]
for file_path in resume_folder.iterdir():
    if file_path.suffix.lower() not in [".pdf", ".docx"]:
        continue
    print("\nProcessing: ",file_path.name)
    resume_text=read_resume(file_path)
    parsed_resume=parsed_resume(resume_text)
    time.sleep(5)
    result=final_score(job, parsed_resume)
    time.sleep(5)
    print("Score: ",result.score)
    all_result.append({
        "name":parsed_resume.name,
        "score":result.score,
        "details":result.details
    })

all_result.sort(
        key=lambda candidate: candidate["score"],
        reverse=True
    )
top_2=all_result[:2]
worst_2=all_result[-2:]
