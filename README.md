# Ecommerce Review Agent

> AI Application Engineering MVP for cross-border e-commerce review monitoring, classification, and workflow automation.

## Project Background

Cross-border e-commerce businesses receive thousands of product reviews daily across multiple platforms (Amazon, Shopify, Aliexpress, etc.) in multiple languages. Manually monitoring, classifying, and routing negative reviews to the correct teams is slow, inconsistent, and expensive.

This project demonstrates an AI-powered automation pipeline that:

1. Ingests reviews from e-commerce platforms
2. Classifies sentiment and issue category using LLM (DeepSeek)
3. Validates structured output with Pydantic schemas
4. Generates reports and flags high-priority cases
5. Orchestrates the workflow via n8n for business team integration

## Business Pain Points

- **High volume**: Hundreds of reviews daily across platforms and countries.
- **Multi-language**: Reviews in English, German, French, Japanese, etc.
- **Manual routing**: Support teams waste time categorizing reviews.
- **Slow response**: Critical negative reviews are not prioritized fast enough.
- **Inconsistent quality**: Different agents classify the same review differently.

## Tech Stack

| Component | Technology |
|-----------|-----------|
| AI Service | Python 3.10 + FastAPI |
| LLM Provider | DeepSeek API (via structured prompts) |
| Data Validation | Pydantic v2 |
| Workflow Engine | n8n |
| Reports | Markdown + Feishu webhook |
| Testing | Pytest + httpx |

## Current Status — Milestone 5

- [x] Project skeleton and package structure
- [x] Pydantic schemas (`ReviewInput`, `ReviewAnalysis`, `BatchAnalysisRequest`, `BatchAnalysisResponse`)
- [x] Config management with `.env` (DeepSeek API, mock mode, timeout, retries)
- [x] DeepSeek LLM client with structured JSON output, retry, and safe fallback
- [x] Mock mode with varied confidence scores for realistic demo (0.50–0.85)
- [x] Review classification workflow with 4 deterministic guardrail rules
- [x] Chinese Markdown daily report generation with statistics
- [x] Batch analysis CLI script (`scripts/run_batch.py`) with rating display
- [x] Comprehensive pytest suite (117 tests, all passing)
- [x] Updated classification prompt with few-shot examples and anti-hallucination rules
- [x] FastAPI `/api/v1/analyze` and `/api/v1/analyze_batch` endpoints
- [x] Demo request script with `--url` support (`scripts/demo_request.py`)
- [x] n8n workflow design and template (Milestone 4)
- [x] **Guardrails** (confidence threshold, contradiction detection, empty field detection, category+rating rules)
- [x] **Error logging** (`outputs/results/error_cases.jsonl` — JSON parse, API timeout, guardrail triggers, validation failures)
- [x] **API key redaction** in error logs (no secrets in log files)
- [x] **Interview documentation** (interview_notes.md with detailed Chinese answers, demo_checklist.md with guardrails demo)

## Quick Start

```bash
# 1. Activate conda environment
conda activate ecommerce-agent
cd /root/autodl-tmp/ecommerce-review-agent

# 2. Install dependencies
python -m pip install -r requirements.txt

# 3. Run tests
pytest -q

# 4. Run batch analysis in mock mode (no API key needed)
python scripts/run_batch.py --mock

# 5. View the generated report
cat outputs/reports/daily_report.md

# 6. (Optional) Run with real DeepSeek API
# Set DEEPSEEK_API_KEY in .env first, then:
python scripts/run_batch.py
```

### Mock Mode vs Real API

| Mode | Command | Requires API Key |
|------|---------|-----------------|
| Mock | `python scripts/run_batch.py --mock` | No |
| Real | `python scripts/run_batch.py` | Yes (set in `.env`) |

Mock mode uses keyword-based classification with varied confidence: clear reviews get 0.80–0.85 (auto-pass), vague/unclassifiable reviews get 0.50 (human review). This produces a realistic demo mix — not all results are flagged.

### Output Files

After running `python scripts/run_batch.py --mock`:

| File | Description |
|------|-------------|
| `outputs/results/review_analysis.json` | Full JSON results with all classifications |
| `outputs/reports/daily_report.md` | Chinese Markdown daily report with statistics |

## FastAPI Service (Milestone 3)

### Start the Server

```bash
# Mock mode — no API key needed (for local demo / interview)
LLM_MOCK_MODE=true uvicorn src.review_agent.api:app --host 0.0.0.0 --port 8000 --reload

# Real mode — requires DEEPSEEK_API_KEY in .env
uvicorn src.review_agent.api:app --host 0.0.0.0 --port 8000 --reload
```

### OpenAPI Docs

Once the server is running, open:

```
http://127.0.0.1:8000/docs
```

### Health Check

```bash
curl http://127.0.0.1:8000/api/v1/health
```

Expected output:

```json
{
  "status": "ok",
  "service": "ecommerce-review-agent"
}
```

### Analyze a Single Review

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "review_id": "r001",
    "platform": "Amazon",
    "product_name": "Wireless Security Camera",
    "rating": 2,
    "review_text": "Battery drains too fast and the night vision is blurry.",
    "country": "US",
    "created_at": "2026-06-01"
  }'
```

Expected output (mock mode):

```json
{
  "review_id": "r001",
  "sentiment": "negative",
  "issue_category": "battery",
  "priority": "high",
  "responsible_team": "product",
  "summary_zh": "用户反馈电池相关问题，评分2。",
  "suggested_action_zh": "建议product团队查看该评论，确认是否需要跟进处理。",
  "confidence": 0.85,
  "needs_human_review": false
}
```

> **Note**: Confidence varies by review clarity. Clear reviews get 0.80–0.85 (auto-pass); vague/unclassifiable reviews get 0.50 (human review).

### Analyze a Batch of Reviews

```bash
curl -X POST http://127.0.0.1:8000/api/v1/analyze_batch \
  -H "Content-Type: application/json" \
  -d '{
    "reviews": [
      {
        "review_id": "r001",
        "platform": "Amazon",
        "product_name": "Camera A",
        "rating": 2,
        "review_text": "Battery drains too fast.",
        "country": "US",
        "created_at": "2026-06-01"
      },
      {
        "review_id": "r002",
        "platform": "Shopify",
        "product_name": "Camera B",
        "rating": 4,
        "review_text": "Great image quality, fast delivery.",
        "country": "DE",
        "created_at": "2026-06-02"
      }
    ]
  }'
```

### Demo Script

```bash
# Full demo (health + single analyze)
python scripts/demo_request.py

# Custom endpoint URL
python scripts/demo_request.py --url http://127.0.0.1:8000/api/v1/analyze

# Health check only
python scripts/demo_request.py --health
```

## Guardrails / Anti-Hallucination Design (Milestone 5)

This project implements **6 layers of hallucination defense** — not one technique, but a layered defense-in-depth:

| # | Layer | Description |
|---|-------|-------------|
| 1 | **JSON-only Prompt** | Prompt demands ONLY valid JSON. No free-form text, no explanation, no markdown fences. Limits the output space. |
| 2 | **Pydantic Validation** | Every LLM output is validated against the `ReviewAnalysis` schema. Type mismatches, missing fields, invalid enums → retry or fallback. |
| 3 | **Auto-Retry** | JSON parse failures and validation failures trigger a retry. Default 2 retries (3 total attempts). |
| 4 | **Safe Fallback** | When all retries fail, a safe fallback result is returned: `issue_category=other, confidence=0.0, needs_human_review=true`. |
| 5 | **Confidence Threshold** | Confidence < 0.6 → automatically flagged for human review regardless of content quality. |
| 6 | **Business Consistency Checks** | Deterministic guardrail rules catch contradictions the LLM might miss (see Human Review Rules below). |

### Human Review Rules

Results are flagged `needs_human_review=true` when ANY of the following conditions are met:

| # | Rule | Trigger Condition |
|---|------|-------------------|
| 1 | **Low Confidence** | `confidence < 0.6` |
| 2 | **Rating/Sentiment Contradiction** | `rating <= 2` but `sentiment != "negative"` |
| 3 | **Uncategorized + Low Rating** | `issue_category == "other"` AND `rating <= 2` |
| 4 | **Empty Summary** | `summary_zh` or `suggested_action_zh` is empty / whitespace |
| 5 | **LLM Parse Failure** | JSON extraction failed after retries → safe fallback used |
| 6 | **API Failure Fallback** | LLM API timeout, network error, or server error → safe fallback used |

> **Design principle**: "宁可多报，不可漏报" — better to over-flag than to miss. All uncertain results go to human review; no false confidence is allowed into business decisions.

### Error Logging

All failures are recorded to `outputs/results/error_cases.jsonl`:

- **Format**: One JSON object per line (JSONL)
- **Fields**: `timestamp`, `review_id`, `error_type`, `error_message`, `fallback_used`, `needs_human_review`
- **Optional**: `raw_output` (truncated to 1000 chars, sanitized)
- **Safety**: API keys, Bearer tokens, and other secrets are **redacted** before writing — no credentials in log files
- **Purpose**: Post-mortem analysis — track down prompt issues, model issues, data quality issues

### Mock Demo (Interview-Ready)

```bash
# Run in mock mode — no API key, no internet, deterministic output
python scripts/run_batch.py --mock

# Check the results
head -n 5 outputs/results/error_cases.jsonl
cat outputs/reports/daily_report.md
```

Mock mode output characteristics:
- **Clear reviews** (explicit keywords, detailed text) → `confidence=0.85`, `needs_human_review=false`
- **Vague/unclassifiable reviews** → `confidence=0.50`, `needs_human_review=true`  
- **Typical ratio**: ~80% auto-pass, ~20% human review (varies with input data)
- Good for demonstrating the guardrail difference between "auto-pass" and "human review needed"

### Mock Mode vs Real API

| Mode | Command | Requires API Key |
|------|---------|-----------------|
| Mock | `LLM_MOCK_MODE=true uvicorn ...` | No |
| Mock | `python scripts/run_batch.py --mock` | No |
| Real | `uvicorn src.review_agent.api:app ...` | Yes (set in `.env`) |
| Real | `python scripts/run_batch.py` | Yes (set in `.env`) |

Mock mode uses keyword-based classification with varied confidence scores (0.50–0.85). Clear reviews auto-pass; vague/unclassifiable reviews are flagged for human review. Designed for local development, testing, and interview demos without an API key.

## n8n Workflow Integration (Milestone 4)

The n8n workflow orchestrates the business automation layer — it triggers review ingestion, calls the FastAPI AI analysis service, aggregates results, and (in future) sends notifications to Feishu.

### Documentation & Template

| Resource | Path | Description |
|----------|------|-------------|
| Workflow Design Doc | `n8n/workflow_design.md` | Full design spec: node sequence, Code Node examples, error handling, interview script |
| Workflow Template | `n8n/review_workflow_template.json` | Best-effort importable JSON (4 nodes: Trigger → Code → HTTP → Code) |

### How to Use

```bash
# 1. Start FastAPI in mock mode (no API key needed)
LLM_MOCK_MODE=true uvicorn src.review_agent.api:app --host 0.0.0.0 --port 8000 --reload

# 2. Verify health
curl http://127.0.0.1:8000/api/v1/health

# 3. Start n8n (in a separate terminal)
export N8N_USER_FOLDER=/root/autodl-tmp/ecommerce-review-agent/.n8n
export N8N_HOST=0.0.0.0
export N8N_PORT=5678
export N8N_LISTEN_ADDRESS=0.0.0.0
export N8N_PROTOCOL=http
export N8N_SECURE_COOKIE=false
n8n start

# 4. Open http://127.0.0.1:5678 → import template or build manually
# 5. Configure HTTP Request node: POST http://127.0.0.1:8000/api/v1/analyze
# 6. Click "Execute Workflow"
```

### Current Limitations (Milestone 4 Scope)

- **No real Feishu integration** — webhook URLs are placeholders (`YOUR_FEISHU_WEBHOOK_URL`)
- **No Amazon/Shopify API** — reviews are mock-generated in a Code Node
- **No production scheduler** — uses Manual Trigger; Schedule Trigger is documented but not configured
- **No RAG or complex Agent** — classification is deterministic Workflow + LLM, not autonomous Agent
- **No database persistence** — results exist only in n8n execution memory

These are documented as future extensions in `n8n/workflow_design.md`.

## Roadmap

| Milestone | Description | Status |
|-----------|-------------|--------|
| 1 | Project skeleton + health check | ✅ Done |
| 2 | Core review analysis (LLM client, workflow, batch run, report) | ✅ Done |
| 3 | FastAPI analysis endpoints (`/analyze`, `/analyze_batch`) | ✅ Done |
| 4 | n8n workflow design and integration | ✅ Done |
| 5 | Guardrails, retry logic, error handling | ✅ Done |
| 6 | Interview packaging (docs, screenshots, demo script) | ⬜ |

## Project Structure

```text
ecommerce-review-agent/
├── README.md
├── CLAUDE.md
├── pyproject.toml
├── requirements.txt
├── .env.example
├── .gitignore
├── src/review_agent/          # Main Python package
│   ├── __init__.py
│   ├── config.py
│   ├── schemas.py
│   ├── api.py
│   ├── workflow.py
│   ├── llm_client.py
│   └── report.py
├── scripts/                   # Runnable scripts
│   ├── run_batch.py
│   └── demo_request.py
├── tests/                     # Pytest test suite
│   ├── test_basic.py
│   ├── test_schema.py
│   ├── test_workflow.py
│   ├── test_report.py
│   └── test_api.py
├── data/mock/                 # Mock data files
│   └── sample_reviews.csv
├── prompts/                   # LLM prompt templates
│   └── review_classification_prompt.md
├── n8n/                       # n8n workflow docs & template
│   ├── workflow_design.md
│   └── review_workflow_template.json
├── docs/                      # Project documentation
│   ├── architecture.md
│   ├── interview_notes.md
│   └── demo_checklist.md
└── outputs/                   # Generated results and reports
    ├── results/
    └── reports/
```
