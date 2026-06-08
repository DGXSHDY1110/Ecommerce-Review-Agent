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

## Current Status — Milestone 3

- [x] Project skeleton and package structure
- [x] Pydantic schemas (`ReviewInput`, `ReviewAnalysis`, `BatchAnalysisRequest`, `BatchAnalysisResponse`)
- [x] Config management with `.env` (DeepSeek API, mock mode, timeout, retries)
- [x] DeepSeek LLM client with structured JSON output, retry, and safe fallback
- [x] Mock mode for testing without real API key
- [x] Review classification workflow with guardrails (confidence threshold, contradiction detection)
- [x] Chinese Markdown daily report generation with statistics
- [x] Batch analysis CLI script (`scripts/run_batch.py`)
- [x] Comprehensive pytest suite (schema, workflow, report, basic, api)
- [x] Updated classification prompt with few-shot examples
- [x] FastAPI `/api/v1/analyze` and `/api/v1/analyze_batch` endpoints
- [x] Demo request script with `--url` support (`scripts/demo_request.py`)
- [ ] n8n workflow integration (Milestone 4)

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

Mock mode uses keyword-based classification and always marks results for human review (confidence=0.5).

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
  "summary_zh": "Mock分析：用户评分2，检测到关键词匹配类别battery。",
  "suggested_action_zh": "Mock建议：请人工复核battery相关评论。",
  "confidence": 0.5,
  "needs_human_review": true
}
```

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

### Mock Mode vs Real API

| Mode | Command | Requires API Key |
|------|---------|-----------------|
| Mock | `LLM_MOCK_MODE=true uvicorn ...` | No |
| Mock | `python scripts/run_batch.py --mock` | No |
| Real | `uvicorn src.review_agent.api:app ...` | Yes (set in `.env`) |
| Real | `python scripts/run_batch.py` | Yes (set in `.env`) |

Mock mode uses keyword-based classification and always marks results for human review (confidence=0.5).  It is designed for local development, testing, and interview demos without an API key.

## Roadmap

| Milestone | Description | Status |
|-----------|-------------|--------|
| 1 | Project skeleton + health check | ✅ Done |
| 2 | Core review analysis (LLM client, workflow, batch run, report) | ✅ Done |
| 3 | FastAPI analysis endpoints (`/analyze`, `/analyze_batch`) | ✅ Done |
| 4 | n8n workflow design and integration | ⬜ |
| 5 | Guardrails, retry logic, error handling | ⬜ |
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
├── n8n/                       # n8n workflow docs & exports
│   └── workflow_design.md
├── docs/                      # Project documentation
│   ├── architecture.md
│   ├── interview_notes.md
│   └── demo_checklist.md
└── outputs/                   # Generated results and reports
    ├── results/
    └── reports/
```
