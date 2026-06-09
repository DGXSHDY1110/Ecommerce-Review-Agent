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

### 4. Guardrails Demo (2 minutes) — Milestone 5

> **Goal**: Demonstrate that this is enterprise-grade AI — not just "the model answered". Every uncertainty is caught, logged, and flagged for human review.

**Pre-flight:**

- [ ] Ensure `outputs/results/error_cases.jsonl` exists or will be generated
- [ ] Run `python scripts/run_batch.py --mock` before demo to have output ready

**Demo steps:**

- [ ] **Show a normal review auto-passing:**
  ```bash
  python -c "
  import json
  with open('outputs/results/review_analysis.json') as f:
      data = json.load(f)
  for r in data['results']:
      if not r['needs_human_review']:
          print(f\"{r['review_id']}: {r['sentiment']} | {r['issue_category']} | confidence={r['confidence']} | needs_human_review={r['needs_human_review']}\")
  "
  ```
  → Point out: "这条评论 confidence=0.85, needs_human_review=False——自动通过，不需要人工干预。这就是 guardrails 的价值：低风险评论自动放行，不浪费人力。"

- [ ] **Show a low-confidence review needing human review:**
  ```bash
  python -c "
  import json
  with open('outputs/results/review_analysis.json') as f:
      data = json.load(f)
  for r in data['results']:
      if r['needs_human_review'] and r['confidence'] < 0.6:
          print(f\"{r['review_id']}: cat={r['issue_category']} | confidence={r['confidence']} | reason: low confidence or unclassifiable\")
  "
  ```
  → Point out: "issue_category=other, confidence=0.50——模型明确说'我不知道这是什么问题'，自动标记需要人工复核。"

- [ ] **Show the guardrail rules in the report:**
  ```bash
  grep -A 15 "人工复核规则说明" outputs/reports/daily_report.md
  ```
  → Walk through each rule: low confidence, rating/sentiment contradiction, uncategorized+low rating, empty summary, API failure, schema validation failure.

- [ ] **Show error_cases.jsonl:**
  ```bash
  head -n 5 outputs/results/error_cases.jsonl
  ```
  → Point out: "每一条记录都有 timestamp, review_id, error_type, error_message, fallback_used, needs_human_review。没有 API key，没有 Authorization header——日志是安全的。"

- [ ] **Explain the fallback mechanism:**
  ```bash
  grep -A 5 "def _safe_fallback" src/review_agent/llm_client.py
  ```
  → Point out: "当 LLM API 调用失败、JSON 解析失败、或者 Schema 校验失败时，返回一个安全的兜底结果：issue_category=other, confidence=0.0, needs_human_review=true。这让下游流程不会因为一个异常而卡死。"

- [ ] **Explain why LLM results should not directly enter business systems:**
  > "LLM 的输出不是确定性的——同一个 Prompt 跑两次可能得到不同结果。如果直接把 LLM 输出写入工单系统、发通知给客服、或者更新库存状态，会出现'同一条评论今天分给 product 团队、明天分给 logistics 团队'的混乱。Guardrails 层就是确保：只有高置信度、业务一致性校验通过的结果，才自动进入下游。其余全部转人工。"

### 4b. Interview Explanation — Guardrails (中文话术)

> 演示 Guardrails 部分时边说边操作：

- [ ] **"这一步展示的是企业级 AI 应用的可控性，不是只追求模型能回答。"**
  → 一边展示自动通过的评论和需要复核的评论。

- [ ] **"低风险评论自动通过，高风险或不确定评论转人工。"**
  → 指出 confidence=0.85 的自动通过，confidence=0.50 的转人工。

- [ ] **"error_cases.jsonl 用于后续排查 prompt、模型、数据和 API 问题。"**
  → `head -n 3 outputs/results/error_cases.jsonl`

- [ ] **"这也是从 Demo 到生产系统的关键差别。"**
  → "Demo 只需要'模型回答了'，生产系统需要'模型回答了什么、对错谁负责、错了怎么办'。Guardrails + error logging + human-in-the-loop 回答的就是这些生产问题。"

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
- [ ] "Notice that high-confidence reviews auto-pass while uncertain ones are flagged `needs_human_review: true` — we never auto-close uncertain classifications."

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
