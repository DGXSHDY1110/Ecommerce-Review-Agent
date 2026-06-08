# Architecture Overview

## System Architecture

```mermaid
graph TD
    A[E-commerce Platforms] -->|Reviews| B[n8n Workflow Engine]
    B -->|HTTP POST| C[FastAPI Service]
    C -->|Prompt + Review| D[DeepSeek LLM API]
    D -->|Structured JSON| C
    C -->|Validate| E[Pydantic Schema]
    E -->|Valid| F[Report Generator]
    E -->|Invalid| G[Retry / Fallback]
    G -->|Fallback Output| F
    F -->|Markdown Report| H[outputs/reports/]
    F -->|Error Cases| I[outputs/results/error_cases.jsonl]
    B -->|Webhook Notification| J[Feishu / Slack]
```

## Component Overview

### 1. FastAPI Service (`src/review_agent/api.py`)

The central AI analysis service. Exposes RESTful endpoints for review classification.

**Endpoints:**

| Method | Path | Description | Status |
|--------|------|-------------|--------|
| GET | `/api/v1/health` | Service health check | ✅ M1 |
| POST | `/api/v1/analyze` | Analyze a single review | ⬜ M3 |
| POST | `/api/v1/analyze_batch` | Analyze multiple reviews | ⬜ M3 |

### 2. LLM Client (`src/review_agent/llm_client.py`)

Abstraction layer for calling the DeepSeek API. Handles:
- Prompt construction with few-shot examples
- API call with retry logic
- Response parsing and JSON extraction

### 3. Schema Layer (`src/review_agent/schemas.py`)

Pydantic models for input/output validation:
- `ReviewInput` — validates incoming review data
- `ReviewOutput` — validates LLM classification output
- `AnalyzeRequest` / `AnalyzeResponse` — API request/response models

### 4. Workflow Orchestrator (`src/review_agent/workflow.py`)

Coordinates the end-to-end analysis pipeline:
1. Read reviews → 2. Call LLM → 3. Validate output → 4. Detect contradictions → 5. Flag for human review

### 5. Report Generator (`src/review_agent/report.py`)

Generates markdown reports and summary statistics from analyzed results.
Distinguishes confirmed results from uncertain cases.

### 6. n8n Workflow Engine

Orchestrates business automation:
- Scheduled triggers: hourly/daily review fetch
- HTTP Request node: calls FastAPI endpoints
- Code nodes: data transformation and aggregation
- Webhook/Feishu nodes: notifications and alerts

### 7. Guardrails

- JSON parse with retry (max 2 attempts)
- Pydantic schema validation
- Confidence threshold filtering
- Contradiction detection (low rating + non-negative sentiment)
- Safe fallback for unparseable outputs
- Error logging to `outputs/results/error_cases.jsonl`

## Data Flow

```mermaid
sequenceDiagram
    participant N as n8n Trigger
    participant A as FastAPI
    participant L as DeepSeek LLM
    participant S as Schema Validator
    participant R as Report Generator

    N->>A: POST /api/v1/analyze
    A->>L: Send prompt + review text
    L-->>A: Return JSON classification
    A->>S: Validate against Pydantic
    alt Valid
        S-->>A: Validated result
        A->>R: Generate report entry
    else Invalid
        S-->>A: Validation error
        A->>L: Retry with stricter prompt
        L-->>A: Second attempt
        alt Still invalid
            A->>A: Apply safe fallback
        end
    end
    A-->>N: Return structured result
    R-->>N: Report ready for distribution
```

## Technology Decisions

| Decision | Rationale |
|----------|-----------|
| DeepSeek (not GPT-4) | Cost-effective for high-volume classification; strong JSON output |
| FastAPI (not Flask) | Native async support, automatic OpenAPI docs, Pydantic integration |
| n8n (not Dify/Coze) | Self-hosted, code-node flexibility, better for business workflow automation |
| Pydantic v2 | Strict schema validation, better error messages, faster than v1 |
| Markdown reports | Human-readable, version-control friendly, easy to send via Feishu |
