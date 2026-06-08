# Demo Checklist

> Step-by-step guide for demonstrating the ecommerce-review-agent project.

## Pre-Demo Setup

- [ ] Conda environment `ecommerce-agent` activated
- [ ] All dependencies installed (`python -m pip install -r requirements.txt`)
- [ ] All tests passing (`pytest -q`)
- [ ] FastAPI server ready to start
- [ ] Sample data available (`data/mock/sample_reviews.csv`)
- [ ] n8n installed and configured (Milestone 4+)
- [ ] .env file configured with API keys (if using real LLM)

## Demo Flow

### 1. Project Overview (1 minute)

- [ ] Explain the business pain point
- [ ] Show the architecture diagram
- [ ] Walk through the project structure
- [ ] Highlight key technology choices

### 2. FastAPI Health Check (30 seconds)

- [ ] Start server: `uvicorn src.review_agent.api:app --host 0.0.0.0 --port 8000`
- [ ] Open browser: `http://127.0.0.1:8000/docs` (OpenAPI docs)
- [ ] Call: `curl http://127.0.0.1:8000/api/v1/health`

### 3. Review Classification Demo (2 minutes)

- [ ] Run batch analysis: `python scripts/run_batch.py`
- [ ] Show input data: `data/mock/sample_reviews.csv`
- [ ] Show output: `outputs/results/review_analysis.json`
- [ ] Show report: `outputs/reports/daily_report.md`
- [ ] Highlight: structured JSON, confidence scores, human review flags

### 4. Guardrails Demo (1 minute)

- [ ] Show error_cases.jsonl when present
- [ ] Explain retry logic
- [ ] Show fallback output for unparseable responses
- [ ] Explain contradiction detection

### 5. n8n Workflow Demo (1 minute)

- [ ] Open n8n dashboard
- [ ] Import workflow template
- [ ] Run Manual Trigger
- [ ] Show HTTP Request node calling FastAPI
- [ ] Show result aggregation

### 6. Q&A Preparation (1 minute)

- [ ] Why Workflow over Agent?
- [ ] How do you reduce hallucination?
- [ ] How do you keep JSON output stable?
- [ ] How would you extend this to Amazon/Shopify/Feishu?

## Post-Demo

- [ ] All browser tabs closed
- [ ] API server stopped
- [ ] No API keys exposed in screenshots

*(Checklist will be updated as each milestone is completed.)*
