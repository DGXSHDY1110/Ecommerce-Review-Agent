# Interview Notes

> Talking points and Q&A preparation for the AI Application Engineering interview.

## Project Positioning

This project demonstrates **AI Application Engineering** competency:
- Understanding real business workflows
- Breaking operations into automatable steps
- Selecting the right AI model and tools for the job
- Building robust LLM-powered services with guardrails
- Integrating AI into existing business systems (n8n, Feishu)

## Key Concepts to Prepare

### Workflow vs Agent

- **Workflow**: Deterministic, pre-defined steps. Reliable and repeatable.
- **Agent**: Autonomous decision-making. Flexible but harder to control.
- This project uses **Workflow + structured LLM calls**, not a fully autonomous Agent.

### n8n vs Dify vs Coze

- **n8n**: Self-hosted, open-source, code-node flexibility, enterprise integration.
- **Dify**: AI-native, RAG-focused, good for prototyping AI apps quickly.
- **Coze**: ByteDance ecosystem, good for Feishu/Lark integration.

### Reducing Hallucination

1. Strict prompt instructions (JSON only, no free-form text)
2. Few-shot examples anchoring expected output
3. Pydantic schema validation as a second-layer check
4. Confidence scoring + human review flag
5. Contradiction detection rules
6. Safe fallback for unparseable outputs

### Stable JSON Output

1. Prompt engineering: explicitly demand JSON, provide format
2. Parse + validate with Pydantic
3. Retry once on failure with stricter instructions
4. Log failures for prompt improvement

### API Failure Handling

1. Connection timeout handling
2. Retry with exponential backoff
3. Safe fallback output when all retries exhausted
4. Error logging for ops visibility

### Extensibility

- **Amazon**: Amazon SP-API for review fetching
- **Shopify**: Shopify Admin API
- **Feishu**: Webhook + Bot integration for notifications
- **Multi-dimensional tables**: Feishu Base for structured result storage

## Metrics to Track

- Classification accuracy vs. human baseline
- JSON parse success rate
- Average confidence score
- Human review rate
- End-to-end latency
- Cost per review analyzed

*(Detailed answers to be expanded before the interview.)*
