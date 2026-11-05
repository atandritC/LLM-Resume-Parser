# LLM Resume Parser

Extracts structured job and resume details, then produces a job-related match score for manual review.

## Setup

Run `uv sync` to install the project dependencies. Put your Groq API key in a local `.env` file:

```env
GROQ_API_KEY=your_key_here
```

The project includes an example job description in `job_description.txt`. Put PDF or DOCX resumes in `resumes/`.

## Run

From the project folder, run:

```bash
uv run llm-resume-parser
```

The program asks you to confirm before sending resume text to Groq. Only continue if you have permission to process those resumes. To use different files or folders, pass `--job-description-file path/to/job.txt` and `--resume-dir path/to/resumes`.

Contact fields are excluded from the matching request. Match scores are decision support for human review, not hiring decisions.
