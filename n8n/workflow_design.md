# n8n Workflow Design

> Workflow design document for the n8n-powered e-commerce review automation.
> Real workflow implementation and integration will be added in Milestone 4.

## Workflow Goal

Automate the end-to-end pipeline:
1. Read/generate review data
2. Send each review to the FastAPI analysis service
3. Aggregate classified results
4. Generate reports and notifications

## Target Workflow Nodes

```
[Manual Trigger] or [Schedule Trigger]
        │
        ▼
[Code Node: Load/Generate Review Data]
        │
        ▼
[Loop Over Items (SplitInBatches)]
        │
        ▼
[HTTP Request Node: POST /api/v1/analyze]
        │
        ▼
[Code Node: Validate & Aggregate Results]
        │
        ▼ (split)
[Output: Save JSON File]    [Webhook Node: Feishu Notification]
```

## Node Details

### 1. Trigger
- **Type**: Manual Trigger (demo) or Schedule Trigger (production: every hour)
- **Purpose**: Start the review monitoring workflow

### 2. Code Node: Load/Generate Review Data
- **Language**: JavaScript
- **Purpose**: Read from CSV, database, or API; shape into array of review objects
- **Output**: Array of review JSON objects matching `ReviewInput` schema

### 3. HTTP Request Node
- **Method**: POST
- **URL**: `http://127.0.0.1:8000/api/v1/analyze`
- **Body**: JSON review object
- **Expected response**: `ReviewOutput` JSON

### 4. Code Node: Validate & Aggregate
- **Language**: JavaScript
- **Purpose**: 
  - Check response status
  - Aggregate results
  - Count by priority, category, team
  - Flag high-priority items for notification

### 5. Output / Webhook
- **Output**: Save aggregated JSON to file
- **Webhook**: Send summary notification to Feishu/Slack (configurable)

## Mock Data Approach (Milestone 4)

The first version will use hardcoded mock review data in the Code Node.
No real platform API connections will be required.

## Environment Variables Required

```bash
# n8n runtime
N8N_USER_FOLDER=/root/autodl-tmp/ecommerce-review-agent/.n8n
N8N_HOST=0.0.0.0
N8N_PORT=5678
N8N_LISTEN_ADDRESS=0.0.0.0
N8N_PROTOCOL=http
N8N_SECURE_COOKIE=false

# FastAPI endpoint (used in HTTP Request node)
REVIEW_AGENT_API=http://127.0.0.1:8000
```

## Export Notes

- Workflow JSON exports will be saved to `n8n/review_workflow_template.json`
- Exports must NOT contain API keys, tokens, or secrets
- Use environment variable references in workflow nodes

## Next Steps (Milestone 4)

1. Start n8n with the configured environment variables
2. Create the workflow manually in n8n UI
3. Test with mock data → FastAPI health check
4. Test full pipeline after Milestone 3 completes
5. Export workflow JSON template

*(This document is a placeholder. Details will be finalized in Milestone 4.)*
