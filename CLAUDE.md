# Ecommerce-Review-Agent Development Rules

You are helping build `ecommerce-review-agent`, a production-style AI application engineering MVP for cross-border e-commerce review monitoring, classification, reporting, and workflow automation.

This project is designed for an AI Application Engineer interview. The focus is not model training from scratch, but business workflow diagnosis, LLM application integration, Agentic Workflow design, n8n automation, FastAPI service development, structured output, and stable system integration.

---

## 1. Project Path

The project root is:

```bash
/root/autodl-tmp/ecommerce-review-agent
```

Before running any command, always make sure you are inside this directory:

```bash
cd /root/autodl-tmp/ecommerce-review-agent
```

Do not create or work in unrelated directories such as:

```text
day1/
day2/
tmp_project/
demo_old/
test_agent_project/
```

Keep all project files inside the standard repository structure.

---

## 2. Python Environment Rules

A dedicated conda environment should be used:

```bash
conda activate ecommerce-agent
```

You must not pollute the base environment.

Strict rules:

1. Never install packages into `base`.
2. Never use global `pip`.
3. Never run `pip install` without confirming the active conda environment.
4. Prefer:

```bash
python -m pip install ...
```

5. Before installing or running anything, check:

```bash
which python
python -V
python -m pip -V
```

6. The Python interpreter should come from the `ecommerce-agent` conda environment.
7. If the environment is not active, stop and tell the user to activate it.
8. Do not run `conda install` unless the user explicitly asks.
9. Do not use `sudo apt install` unless the user explicitly asks.
10. Add project dependencies to `requirements.txt` or `pyproject.toml` instead of installing random packages silently.

Expected Python environment check:

```bash
conda activate ecommerce-agent
cd /root/autodl-tmp/ecommerce-review-agent

which python
python -V
python -m pip -V
```

The Python path should look similar to:

```text
/root/miniconda3/envs/ecommerce-agent/bin/python
```

---

## 3. Node.js, Claude Code, and n8n Rules

This project may use:

* Claude Code as the coding assistant
* DeepSeek API as the LLM provider
* n8n as the workflow automation engine

Before running Node.js-related commands, check:

```bash
node -v
npm -v
```

Claude Code should be used only as a development assistant. Do not let Claude Code rewrite the whole project at once.

n8n should be used for workflow orchestration only. The core AI logic should live in the Python/FastAPI service.

Recommended n8n environment variables:

```bash
export N8N_USER_FOLDER=/root/autodl-tmp/ecommerce-review-agent/.n8n
export N8N_HOST=0.0.0.0
export N8N_PORT=5678
export N8N_LISTEN_ADDRESS=0.0.0.0
export N8N_PROTOCOL=http
export N8N_SECURE_COOKIE=false
```

Start n8n from the project root:

```bash
cd /root/autodl-tmp/ecommerce-review-agent
n8n start
```

Do not store n8n runtime data, credentials, or secrets in Git.

The `.n8n/` directory must be ignored by Git.

---

## 4. Secret and API Key Rules

Never commit secrets.

Do not put any of the following into the repository:

```text
DeepSeek API keys
OpenAI API keys
Claude API keys
Feishu webhook tokens
Amazon API credentials
Shopify API credentials
Cookie values
Access tokens
Private company data
```

Use `.env` for local development and `.env.example` for safe templates.

`.env` must be ignored by Git.

Allowed `.env.example` format:

```env
DEEPSEEK_API_KEY=your_deepseek_api_key_here
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash

APP_HOST=0.0.0.0
APP_PORT=8000

FEISHU_WEBHOOK_URL=your_feishu_webhook_url_here
```

Never hard-code API keys in Python files, n8n workflow exports, README, tests, or docs.

---

## 5. Development Scope Rules

1. Do not implement the whole project at once.
2. Only complete the specific milestone requested by the user.
3. Before coding, read the relevant design files under `docs/`.
4. Keep the repository structure clean and standard.
5. Prefer mock data and deterministic logic first. Real platform APIs can be added later.
6. LLM calls should be wrapped behind a clean client interface.
7. Every milestone must include a clear verification method.
8. Add or update tests whenever possible.
9. Do not silently change project architecture without explaining why.
10. Do not introduce unnecessary heavy frameworks.

After finishing each milestone, summarize:

```text
- files created or modified
- how to run
- how to test
- what remains unfinished
```

---

## 6. Project Goal

The project goal is to build a demonstrable AI workflow MVP:

```text
Cross-border e-commerce review data
        ↓
FastAPI AI analysis service
        ↓
DeepSeek LLM structured classification
        ↓
JSON schema validation and fallback
        ↓
n8n workflow orchestration
        ↓
result table / report / notification
```

The MVP should show that the developer can:

1. Diagnose business workflows.
2. Identify repetitive, high-frequency, standardizable tasks.
3. Choose the correct AI model and tool.
4. Use Prompt Engineering and Few-shot examples.
5. Build an Agentic Workflow.
6. Integrate LLM API, Python service, n8n, and business data.
7. Handle failure cases and unstable LLM outputs.
8. Explain the project clearly in an interview.

---

## 7. Recommended Repository Structure

Use this structure unless the user explicitly changes it:

```text
ecommerce-review-agent/
├── README.md
├── CLAUDE.md
├── .gitignore
├── .env.example
├── requirements.txt
├── pyproject.toml
├── data/
│   └── sample_reviews.csv
├── prompts/
│   └── review_classification_prompt.md
├── src/
│   └── review_agent/
│       ├── __init__.py
│       ├── config.py
│       ├── schemas.py
│       ├── llm_client.py
│       ├── workflow.py
│       ├── report.py
│       └── api.py
├── scripts/
│   ├── run_batch.py
│   ├── validate_output.py
│   └── demo_request.py
├── n8n/
│   ├── workflow_design.md
│   └── review_workflow_template.json
├── outputs/
│   ├── results/
│   └── reports/
├── docs/
│   ├── architecture.md
│   ├── interview_notes.md
│   └── demo_checklist.md
└── tests/
    ├── test_schema.py
    ├── test_workflow.py
    └── test_report.py
```

Do not create unrelated folders.

---

## 8. Core Business Scenario

The main business scenario is:

```text
Cross-border e-commerce negative review monitoring and automatic classification.
```

Typical input fields:

```text
review_id
platform
product_name
rating
review_text
country
created_at
```

Expected AI output fields:

```text
review_id
sentiment
issue_category
priority
responsible_team
summary_zh
suggested_action_zh
confidence
needs_human_review
```

Recommended issue categories:

```text
logistics
product_quality
battery
image_quality
customer_service
price
description_mismatch
other
```

Recommended responsible teams:

```text
operations
product
supply_chain
customer_service
marketing
unknown
```

---

## 9. LLM Output Rules

LLM output must be structured JSON.

The LLM must not output free-form explanations when the API expects JSON.

Required behavior:

1. Use a strict prompt.
2. Use Few-shot examples where helpful.
3. Parse model output with JSON parser.
4. Validate output with Pydantic schema.
5. Retry once if parsing fails.
6. If it still fails, return a safe fallback:

```json
{
  "issue_category": "other",
  "priority": "medium",
  "confidence": 0.0,
  "needs_human_review": true
}
```

7. If confidence is below threshold, set:

```json
{
  "needs_human_review": true
}
```

8. If `rating <= 2` but model sentiment is not `negative`, mark it for human review.

---

## 10. Anti-Hallucination and Guardrail Rules

This project should demonstrate enterprise AI application reliability.

Use the following guardrails:

1. The model can only classify based on the provided review text.
2. The model must not invent external facts.
3. The model must not claim platform statistics unless provided.
4. The model must output structured JSON.
5. All JSON must pass schema validation.
6. Low-confidence results must be marked for human review.
7. Contradictory results must be marked for human review.
8. API failures must be logged.
9. Invalid LLM outputs must be logged.
10. The final report should distinguish confirmed results from uncertain cases.

Failure cases should be written to:

```text
outputs/results/error_cases.jsonl
```

---

## 11. FastAPI Rules

FastAPI should expose the AI analysis service.

Required endpoints:

```text
GET /api/v1/health
POST /api/v1/analyze
POST /api/v1/analyze_batch
```

Expected behavior:

### GET /api/v1/health

Returns:

```json
{
  "status": "ok",
  "service": "ecommerce-review-agent"
}
```

### POST /api/v1/analyze

Input:

```json
{
  "review_id": "r001",
  "platform": "Amazon",
  "product_name": "Wireless Security Camera",
  "rating": 2,
  "review_text": "Battery drains too fast and the night vision is blurry.",
  "country": "US",
  "created_at": "2026-06-01"
}
```

Output:

```json
{
  "review_id": "r001",
  "sentiment": "negative",
  "issue_category": "battery",
  "priority": "high",
  "responsible_team": "product",
  "summary_zh": "用户反馈电池续航差且夜视模糊。",
  "suggested_action_zh": "建议产品团队检查该型号电池投诉率和夜视表现。",
  "confidence": 0.86,
  "needs_human_review": false
}
```

Start API server:

```bash
uvicorn src.review_agent.api:app --host 0.0.0.0 --port 8000 --reload
```

---

## 12. n8n Workflow Rules

The n8n workflow should demonstrate business automation.

Minimum workflow nodes:

```text
Manual Trigger
        ↓
Code Node: generate or read review data
        ↓
HTTP Request: call FastAPI /api/v1/analyze
        ↓
Code Node: aggregate results
        ↓
Output / Feishu Webhook / Report
```

The first version may use mock data.

Do not require real Amazon, Shopify, or Feishu credentials for the MVP.

The workflow should be documented in:

```text
n8n/workflow_design.md
```

If exporting n8n workflow JSON, save it to:

```text
n8n/review_workflow_template.json
```

Make sure workflow exports do not include secrets.

---

## 13. Documentation Rules

Keep documentation interview-oriented.

Required docs:

```text
README.md
docs/architecture.md
docs/interview_notes.md
docs/demo_checklist.md
n8n/workflow_design.md
```

`README.md` should include:

```text
project background
business pain point
system architecture
tech stack
quick start
API usage
n8n workflow
input and output examples
guardrails
demo checklist
interview talking points
future extensions
```

`docs/interview_notes.md` should cover:

```text
why this is an AI Application Engineering project
Workflow vs Agent
n8n vs Dify vs Coze
how to reduce hallucination
how to keep JSON output stable
how to handle API failures
how to evaluate workflow effectiveness
how this can extend to Amazon / Shopify / Feishu
```

---

## 14. Testing Rules

Add tests whenever possible.

Minimum tests:

```text
tests/test_schema.py
tests/test_workflow.py
tests/test_report.py
```

Tests should avoid real API calls by default.

Use mock LLM responses for unit tests.

Do not require a valid DeepSeek API key to run basic tests.

Standard verification commands:

```bash
conda activate ecommerce-agent
cd /root/autodl-tmp/ecommerce-review-agent

which python
python -V
python -m pip -V

python -m compileall src scripts tests
pytest -q
git status
git diff --stat
```

If tests fail, fix only the current milestone's related files.

---

## 15. Standard Run Commands

Run batch analysis:

```bash
conda activate ecommerce-agent
cd /root/autodl-tmp/ecommerce-review-agent

python scripts/run_batch.py
```

Start FastAPI:

```bash
conda activate ecommerce-agent
cd /root/autodl-tmp/ecommerce-review-agent

uvicorn src.review_agent.api:app --host 0.0.0.0 --port 8000 --reload
```

Test health endpoint:

```bash
curl http://127.0.0.1:8000/api/v1/health
```

Run demo request:

```bash
python scripts/demo_request.py
```

Start n8n:

```bash
conda activate ecommerce-agent
cd /root/autodl-tmp/ecommerce-review-agent

export N8N_USER_FOLDER=/root/autodl-tmp/ecommerce-review-agent/.n8n
export N8N_HOST=0.0.0.0
export N8N_PORT=5678
export N8N_LISTEN_ADDRESS=0.0.0.0
export N8N_PROTOCOL=http
export N8N_SECURE_COOKIE=false

n8n start
```

---

## 16. Git Rules

Use Git after each milestone.

Before commit:

```bash
git status
git diff --stat
```

Do not commit:

```text
.env
.n8n/
outputs/
API keys
tokens
private data
large temporary files
```

Recommended `.gitignore`:

```gitignore
.env
__pycache__/
*.pyc
.pytest_cache/
.DS_Store
.n8n/
outputs/
*.log
```

Recommended milestone commits:

```bash
git add .
git commit -m "init ecommerce review agent skeleton"

git add .
git commit -m "add review classification workflow"

git add .
git commit -m "add fastapi analysis service"

git add .
git commit -m "add n8n workflow documentation"

git add .
git commit -m "add guardrails and interview notes"
```

---

## 17. Milestone Rules

### Milestone 1: Project Skeleton

Create:

```text
README.md
CLAUDE.md
requirements.txt
pyproject.toml
.env.example
data/sample_reviews.csv
prompts/review_classification_prompt.md
basic src package
basic tests
```

Verification:

```bash
python -m compileall src tests
pytest -q
```

---

### Milestone 2: Core Review Analysis

Implement:

```text
schemas.py
config.py
llm_client.py
workflow.py
scripts/run_batch.py
report.py
```

Expected output:

```text
outputs/results/review_analysis.json
outputs/reports/daily_report.md
```

Verification:

```bash
python scripts/run_batch.py
cat outputs/reports/daily_report.md
pytest -q
```

---

### Milestone 3: FastAPI Service

Implement:

```text
src/review_agent/api.py
scripts/demo_request.py
```

Verification:

```bash
uvicorn src.review_agent.api:app --host 0.0.0.0 --port 8000 --reload
curl http://127.0.0.1:8000/api/v1/health
python scripts/demo_request.py
```

---

### Milestone 4: n8n Workflow

Create:

```text
n8n/workflow_design.md
n8n/review_workflow_template.json
```

The workflow should call:

```text
POST http://127.0.0.1:8000/api/v1/analyze
```

Verification:

```text
Open n8n
Run Manual Trigger
Confirm HTTP Request calls FastAPI successfully
Confirm structured result is returned
```

---

### Milestone 5: Guardrails and Failure Handling

Add:

```text
JSON parsing retry
Pydantic validation
confidence threshold
human review flag
error_cases.jsonl
interview notes
```

Verification:

```bash
python scripts/run_batch.py
pytest -q
```

---

### Milestone 6: Interview Packaging

Complete:

```text
README.md
docs/architecture.md
docs/interview_notes.md
docs/demo_checklist.md
screenshots or placeholders
```

Verification:

```text
The user can explain the project in 2 minutes.
The user can demo FastAPI and n8n.
The user can answer Workflow vs Agent, RAG, Prompt, guardrails, and API integration questions.
```

---

## 18. Interview Positioning

This project should be explained as:

```text
An AI Application Engineering MVP that converts a repetitive cross-border e-commerce operation workflow into an automated LLM-powered business process.
```

Do not describe it as:

```text
a pure model training project
a toy chatbot
a simple prompt demo
```

Emphasize:

```text
business workflow diagnosis
model and tool selection
Prompt Engineering
structured output
FastAPI integration
n8n workflow automation
guardrails
failure handling
report generation
future Feishu/Amazon/Shopify integration
```

---

## 19. Final Milestone Summary Format

After each milestone, respond using this format:

```text
Milestone completed: <name>

Files created or modified:
- ...

How to run:
- ...

How to test:
- ...

Verification result:
- ...

What remains unfinished:
- ...
```

Do not claim success unless verification commands have actually passed.

---

## 20. Important Principle

The purpose of this project is not to show that the model is powerful.

The purpose is to show:

```text
I can understand a real business workflow,
break it into executable steps,
choose the right AI model and tools,
connect APIs and workflow engines,
control unstable LLM outputs,
and deliver a stable automation system.
```
