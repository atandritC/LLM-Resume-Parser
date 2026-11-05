"""Parse resumes and compare them with a job description using Groq."""

import argparse
import json
import os
from pathlib import Path
from typing import Any

import fitz
from docx import Document
from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel, Field


DEFAULT_MODEL = "openai/gpt-oss-120b"


class Job(BaseModel):
    role: str
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    minimum_experience: float | None = None
    education_requirements: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)


class Experience(BaseModel):
    company: str | None = None
    role: str | None = None
    duration: str | None = None
    description: str | None = None
    skills_used: list[str] = Field(default_factory=list)


class Resume(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    total_experience_years: float | None = None
    skills: list[str] = Field(default_factory=list)
    experience: list[Experience] = Field(default_factory=list)
    education: list[str] = Field(default_factory=list)
    projects: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


class MatchResult(BaseModel):
    score: float = Field(ge=0, le=100)
    details: dict[str, Any] = Field(default_factory=dict)


def _request_json(client: Groq, model: str, messages: list[dict[str, str]]) -> dict[str, Any]:
    """Request a JSON response and parse the first completion choice."""
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("The model returned an empty response.")
    return json.loads(content)


def parse_job_description(client: Groq, model: str, job_description: str) -> Job:
    system_prompt = f"""You extract job requirements into structured data.
Return only JSON matching this schema: {Job.model_json_schema()}
Do not invent information. Use null for unknown experience and empty lists
when a list has no information.
"""
    data = _request_json(
        client,
        model,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Analyze this job description:\n\n{job_description}"},
        ],
    )
    return Job.model_validate(data)


def parse_resume(client: Groq, model: str, resume_text: str) -> Resume:
    system_prompt = f"""You extract factual information from resumes.
Return only JSON matching this schema: {Resume.model_json_schema()}
Do not invent information. Use null for unknown scalar fields and empty
lists when information is missing. Include internships in experience.
"""
    data = _request_json(
        client,
        model,
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Parse this resume:\n\n{resume_text}"},
        ],
    )
    return Resume.model_validate(data)


def score_resume(client: Groq, model: str, job: Job, resume: Resume) -> MatchResult:
    # Contact details are not relevant to matching, so leave them out of this request.
    resume_for_matching = resume.model_dump(exclude={"name", "email", "phone"})
    system_prompt = f"""Compare the job requirements with the candidate's qualifications.
Return only JSON matching this schema: {MatchResult.model_json_schema()}
Set score from 0 to 100 and provide concise evidence in details, including
matching skills, missing important skills, experience fit, and a short verdict.
Base the score only on job-related evidence. Do not infer protected traits.
"""
    data = _request_json(
        client,
        model,
        [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Job requirements:\n{job.model_dump_json(indent=2)}\n\n"
                    f"Resume details:\n{json.dumps(resume_for_matching, indent=2)}"
                ),
            },
        ],
    )
    return MatchResult.model_validate(data)


def read_pdf(file_path: Path) -> str:
    with fitz.open(file_path) as document:
        return "\n".join(page.get_text() for page in document)


def read_docx(file_path: Path) -> str:
    document = Document(file_path)
    parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
    for table in document.tables:
        for row in table.rows:
            parts.extend(cell.text for cell in row.cells if cell.text.strip())
    return "\n".join(parts)


def read_resume(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return read_pdf(file_path)
    if suffix == ".docx":
        return read_docx(file_path)
    raise ValueError(f"Unsupported resume format: {file_path.suffix}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Parse resumes and compare them to a job description.")
    parser.add_argument(
        "--job-description-file",
        type=Path,
        default=Path("job_description.txt"),
        help="Text file containing the job description (default: job_description.txt)",
    )
    parser.add_argument("--resume-dir", type=Path, default=Path("resumes"), help="Folder containing PDF or DOCX resumes")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Groq model name")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if not args.job_description_file.is_file():
        raise SystemExit(f"Job description file not found: {args.job_description_file}")
    if not args.resume_dir.is_dir():
        raise SystemExit(f"Resume folder not found: {args.resume_dir}")

    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise SystemExit("GROQ_API_KEY is missing. Add it to your local .env file.")

    client = Groq(api_key=api_key)
    job_description = args.job_description_file.read_text(encoding="utf-8")
    job = parse_job_description(client, args.model, job_description)

    results: list[dict[str, Any]] = []
    resume_files = sorted(
        path for path in args.resume_dir.iterdir() if path.suffix.lower() in {".pdf", ".docx"}
    )
    if not resume_files:
        raise SystemExit(f"No PDF or DOCX resumes found in {args.resume_dir}")

    print("Resume text will be sent to Groq for parsing. Only continue if you have permission to process these files.")
    if input("Continue? [y/N]: ").strip().lower() not in {"y", "yes"}:
        print("Cancelled.")
        return

    for file_path in resume_files:
        print(f"Processing {file_path.name}...")
        try:
            resume_text = read_resume(file_path)
            if not resume_text.strip():
                raise ValueError("No text could be extracted from this file.")
            resume = parse_resume(client, args.model, resume_text)
            result = score_resume(client, args.model, job, resume)
            results.append(
                {
                    "name": resume.name or file_path.stem,
                    "score": result.score,
                    "details": result.details,
                }
            )
        except Exception as exc:
            print(f"Skipping {file_path.name}: {exc}")

    results.sort(key=lambda candidate: candidate["score"], reverse=True)
    print("\nResults (review these manually; scores are not hiring decisions):")
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
