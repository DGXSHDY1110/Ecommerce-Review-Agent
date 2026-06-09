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

### 2. FastAPI Service Demo (2 minutes)

- [ ] Start server (mock mode): `LLM_MOCK_MODE=true uvicorn src.review_agent.api:app --host 0.0.0.0 --port 8000`
- [ ] Open browser: `http://127.0.0.1:8000/docs` (OpenAPI docs — Swagger UI)
- [ ] Show health: `curl http://127.0.0.1:8000/api/v1/health`
- [ ] Show single analyze via Swagger UI "Try it out" or curl:
  ```bash
  curl -X POST http://127.0.0.1:8000/api/v1/analyze \
    -H "Content-Type: application/json" \
    -d '{"review_id":"r001","platform":"Amazon","product_name":"Camera","rating":2,"review_text":"Battery drains too fast.","country":"US","created_at":"2026-06-01"}'
  ```
- [ ] Show batch analyze via curl or Swagger UI
- [ ] Run demo script: `python scripts/demo_request.py`
- [ ] Explain: mock mode uses keywords, real mode calls DeepSeek LLM
- [ ] Explain: n8n will call these same `/api/v1/analyze` endpoints via HTTP Request nodes

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

### 5. n8n Workflow Demo (2 minutes) — Milestone 4

**Pre-flight (before demo):**

- [ ] Conda environment activated: `conda activate ecommerce-agent`
- [ ] FastAPI running in mock mode:
  ```bash
  LLM_MOCK_MODE=true uvicorn src.review_agent.api:app --host 0.0.0.0 --port 8000 --reload
  ```
- [ ] Health check passing: `curl http://127.0.0.1:8000/api/v1/health`
- [ ] n8n started:
  ```bash
  export N8N_USER_FOLDER=/root/autodl-tmp/ecommerce-review-agent/.n8n
  export N8N_HOST=0.0.0.0
  export N8N_PORT=5678
  export N8N_LISTEN_ADDRESS=0.0.0.0
  export N8N_PROTOCOL=http
  export N8N_SECURE_COOKIE=false
  n8n start
  ```

**Demo steps:**

- [ ] Open browser: `http://127.0.0.1:5678` — show n8n dashboard
- [ ] **Option A** — Import workflow template:
  - Click "Import from File" → select `n8n/review_workflow_template.json`
  - If import fails, explain: "Templates are version-sensitive; I'll build it manually to show I understand the nodes."
- [ ] **Option B** — Create workflow manually (interview-safe):
  1. Add Manual Trigger node
  2. Add Code Node: paste "Generate Mock Reviews" code from `n8n/workflow_design.md` §6.1
  3. Add HTTP Request Node: POST `http://127.0.0.1:8000/api/v1/analyze`, Content-Type JSON, body `={{ $json }}`
  4. Add Code Node: paste "Aggregate Results" code from `n8n/workflow_design.md` §6.2
  5. Add NoOp node: "Display Report"
  6. Connect all nodes in sequence
  7. Save workflow: "Ecommerce Review Agent — Daily Classification"
- [ ] Click **"Execute Workflow"** (Manual Trigger)
- [ ] Show each node turning green in sequence
- [ ] Click on "Call Analyze API" node → show the HTTP response JSON (sentiment, issue_category, etc.)
- [ ] Click on "Aggregate Results" node → show:
  - `total_reviews`, `negative_reviews`, `high_priority_reviews`
  - `needs_human_review_count`
  - `category_distribution`, `responsible_team_distribution`
  - `report_summary` (formatted text)
- [ ] Click on "Display Report" node → show the final aggregated output

**Interview explanation while demoing:**

- [ ] "Manual Trigger → Code Node generates mock data → HTTP Request calls the same FastAPI endpoint you saw earlier → Code Node aggregates everything into a daily report."
- [ ] "In production, the Manual Trigger becomes a Schedule Trigger at 9:07 AM daily."
- [ ] "The Code Nodes are JavaScript — n8n gives you full programmatic control, not just drag-and-drop."
- [ ] "Notice every review with `needs_human_review: true` is flagged separately — we never auto-close uncertain classifications."

**Troubleshooting during demo:**

- [ ] If HTTP Request fails: "Let me check the FastAPI service is running..." → health check curl
- [ ] If Code Node errors: "Let me verify the JavaScript syntax..." → check n8n Code Node editor
- [ ] If n8n not responding: restart n8n with the correct env vars

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
