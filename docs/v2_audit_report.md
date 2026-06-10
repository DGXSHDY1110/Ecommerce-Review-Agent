# V2-M0 项目全面审查报告

> 审查日期：2026-06-10
> 审查范围：ecommerce-review-agent 全项目（只读，未修改任何代码）
> 审查目的：评估当前 V1 项目在面试场景中的可信度，识别问题，制定 V2 改造路线

---

## 1. 当前目录结构（4 层以内）

```
ecommerce-review-agent/
├── README.md
├── CLAUDE.md
├── .gitignore
├── .env.example
├── .env                                    # 存在，含真实 API key（未纳入 Git）
├── requirements.txt
├── pyproject.toml
├── src/
│   └── review_agent/
│       ├── __init__.py                     # __version__ = "0.1.0"
│       ├── config.py                       # Settings, get_settings()
│       ├── schemas.py                      # ReviewInput, ReviewAnalysis, Batch*
│       ├── api.py                          # FastAPI app (3 endpoints)
│       ├── workflow.py                     # analyze_review, apply_guardrails
│       ├── llm_client.py                   # LLMClient (real + mock)
│       ├── report.py                       # generate_daily_report()
│       └── utils.py                        # log_error_case, _sanitise_output
├── scripts/
│   ├── run_batch.py                        # CLI batch runner (--mock flag)
│   └── demo_request.py                     # curl demo against FastAPI
├── tests/
│   ├── __init__.py
│   ├── test_basic.py                       # Package imports, basic health
│   ├── test_schema.py                      # ReviewInput, ReviewAnalysis, Batch
│   ├── test_workflow.py                    # Mock-mode workflow tests
│   ├── test_api.py                         # FastAPI endpoints (TestClient)
│   ├── test_report.py                      # Report generation
│   ├── test_guardrails.py                  # Isolated guardrail rule tests
│   └── test_error_logging.py               # Error log write, sanitise
├── data/
│   └── mock/
│       └── sample_reviews.csv              # 10 mock reviews
├── prompts/
│   └── review_classification_prompt.md     # Full system prompt + few-shot
├── n8n/
│   ├── workflow_design.md                  # Comprehensive design doc
│   └── review_workflow_template.json       # 5-node template (4 nodes + NoOp)
├── docs/
│   ├── architecture.md
│   ├── interview_notes.md                  # Extensive Chinese Q&A prep
│   └── demo_checklist.md                   # Step-by-step demo guide
└── outputs/
    ├── results/
    │   ├── review_analysis.json            # Last run output (10 reviews)
    │   └── error_cases.jsonl               # 170 lines (mostly guardrail noise)
    └── reports/
        └── daily_report.md                 # Last generated Markdown report
```

**评估：** 目录结构完全符合 CLAUDE.md 中推荐的结构。唯一差异：`data/sample_reviews.csv` 实际位于 `data/mock/` 子目录而非直接在 `data/` 下。

---

## 2. 当前核心文件说明

### schemas.py
- **4 个核心模型：** `ReviewInput`（输入校验）、`ReviewAnalysis`（AI 输出）、`BatchAnalysisRequest` / `BatchAnalysisResponse`
- **3 个 API 模型：** `AnalyzeRequest`、`AnalyzeResponse`、`HealthResponse`
- 定义了全局 valid value sets（VALID_SENTIMENTS 等）但**未在 Pydantic 模型中强制枚举校验**（字段用 `str` 类型而非 `Literal`）
- `ReviewInput` 有 `field_validator` 用于 review_text 非空校验
- **问题：** 缺少 `evidence` 字段（模型判断依据），缺少 `is_mock` 标记

### config.py
- 从 `.env` 加载配置（dotenv）
- 支持：DeepSeek API 三个参数、LLM timeout/retries/mock_mode、App host/port、Feishu webhook、confidence_threshold、retry_max_attempts
- `llm_mock_mode` 默认为 `false`，但**实际运行时如果没有 API key 会自动切到 mock**
- **问题：** `low_rating_threshold` 是硬编码常量（2），不应在 config 类中

### llm_client.py
- **核心文件，共 493 行**，实现了 mock 和 real 两种模式
- **Mock 模式（`_mock_analyze`）**：基于关键词的规则分类，confidence 0.50/0.80/0.85 三档
- **Real 模式（`_call_api_with_retry`）**：完整的 DeepSeek Chat Completions API 调用
- `_extract_json`：三层 JSON 提取策略（代码块 → 外括号 → 直接解析）
- `_safe_fallback`：解析失败时的安全兜底
- `_safe_error_message`：API key 脱敏
- `_load_system_prompt`：动态从 prompts/ 目录加载 system prompt
- **3 个关键发现：**
  1. **第 81-83 行：** 无 API key 时自动静默切换到 mock 模式（只打 warning log）
  2. **第 145-146 行：** Mock 的 summary_zh 是模板字符串 `f"用户反馈{category_display}问题，评分{rating}。"` 而非真正的 LLM 生成中文摘要
  3. **第 149 行：** suggested_action_zh 使用 `f"建议{responsible_team}团队查看该评论，确认是否需要跟进处理。"` — **"建议unknown团队查看该评论"** 这种输出暴露了 mock 本质

### workflow.py
- `analyze_review`：单条评论管道（LLM → guardrails）
- `analyze_reviews_batch`：批量顺序处理，单条失败不中断
- `analyze_batch_request`：batch 请求入口
- `apply_guardrails`：5 条确定性规则
  - **Rule 5 "high_priority_noted"** 每次高优先级都触发，这是噪声日志的主要来源（error_cases.jsonl 中 90%+ 的条目）
- **问题：** guardrails 的 `log_error_case` 只在 `needs_human_review=True` 时调用，但 `high_priority_noted` 规则**不区分是否真的需要复核**就记录日志

### report.py
- `generate_daily_report`：生成 7 段中文 Markdown 报告（总览、类别分布、团队分布、高优先级详情、人工复核列表、规则说明、负面评论详情）
- 接受 `rating_map` 参数用于在人工复核表格中显示原始评分
- **问题：** `rating_map` 参数在 report.py 的类型是 `Optional[dict[str, int]]`，但调用方（run_batch.py）传入的 key 和 review_id 类型可能不匹配

### api.py
- FastAPI app，3 个端点：`GET /api/v1/health`、`POST /api/v1/analyze`、`POST /api/v1/analyze_batch`
- 全局异常处理器（防止 traceback 泄露）
- 路由处理层极薄（直接委托给 workflow），设计良好
- **问题：** API 不返回 `is_mock` 字段，调用方（n8n/客户端）无法判断返回结果是真实 LLM 还是 mock

### run_batch.py
- CLI 脚本，支持 `--mock` 和 `--input` 和 `--output-*` 参数
- 逻辑清晰：读 CSV → 创建 client → 调用 workflow → 写 JSON → 写 report
- **问题：** 无 API key 时自动切 mock 并打印 warning，但不清楚——用户可能不知道自己在跑 mock

### n8n/workflow_design.md
- **文档质量极高**，包含：业务目标、先决条件、节点序列（Mermaid 图）、每个节点的配置和面试话术、Code Node JS 代码、错误处理策略表、面试 2 分钟脚本、未来扩展路线图
- **问题：** 文档设计得极其详细，但当前 JSON 模板只有最基础的 5 个节点

---

## 3. 哪些地方仍然是 Mock

### 3.1 Mock 模式开启位置

| 位置 | 如何开启 | 效果 |
|------|----------|------|
| **config.py:20** | 环境变量 `LLM_MOCK_MODE=true` | `Settings.llm_mock_mode = True` |
| **llm_client.py:78-79** | `if self.mock_mode:` | 直接走 `_mock_analyze()` |
| **llm_client.py:81-83** | `if not self.api_key:` | **无 API key 时自动静默切 mock** |
| **run_batch.py:138-139** | `--mock` 命令行参数 | 设置 `settings.llm_mock_mode = True` |
| **run_batch.py:142-144** | 无 API key 时 | 自动切 mock 并打印 warning |
| **API 启动** | `LLM_MOCK_MODE=true uvicorn ...` | API 所有请求走 mock |

### 3.2 Mock 逻辑所在文件

- **llm_client.py `_mock_analyze()` (L88-L152)：** 核心 mock 逻辑
- **llm_client.py `_classify_category()` (L192-L208)：** 关键词分类
- **llm_client.py `_compute_mock_confidence()` (L154-L191)：** Mock 置信度计算

### 3.3 是否默认 Mock

**结论：几乎总是 mock。**

| 场景 | 实际行为 |
|------|----------|
| `python scripts/run_batch.py`（无 --mock，无 API key） | **自动切 mock** |
| `python scripts/run_batch.py --mock` | 明确 mock |
| `python scripts/run_batch.py`（有 API key） | 真实调用 DeepSeek |
| `uvicorn ...` 启动（无 LLM_MOCK_MODE，无 API key） | **自动切 mock** |
| `uvicorn ...` 启动（LLM_MOCK_MODE=true） | 明确 mock |
| README.md 的 Quick Start 第 4 步 | `python scripts/run_batch.py --mock` |

**关键问题：** 无 API key 时的自动切换虽然避免了崩溃，但**让用户不自知地在 mock 模式下运行**。WARNING 日志仅写入 Python logger，CLI 输出只有一行 `⚠️ DEEPSEEK_API_KEY not set. Switching to mock mode automatically.`，但这些都不够醒目。

### 3.4 哪些输出暴露了 Mock 本质

1. **`summary_zh`** 是模板字符串而非自然语言：`"用户反馈电池相关问题，评分2。"` — LLM 不会写"评分2"这样的机械表达
2. **`suggested_action_zh`** 有 "建议unknown团队查看该评论" — 真实 LLM 不会输出 `unknown` 团队
3. **所有 confidence 只有 3 个值：** 0.50、0.80、0.85 — 真实 LLM 的 confidence 应更分散
4. **没有 `evidence` 字段**说明模型为什么做这个判断
5. **输出中没有 `is_mock` 标记**——调用方完全不知道结果是 mock 还是 real

---

## 4. 当前 API 接口

### GET /api/v1/health

| 属性 | 说明 |
|------|------|
| 输入 | 无 |
| 输出 | `{"status": "ok", "service": "ecommerce-review-agent"}` |
| 调用 workflow.py | 否 |
| 状态 | ✅ 正常工作 |

### POST /api/v1/analyze

| 属性 | 说明 |
|------|------|
| 输入 | `ReviewInput`（review_id, platform, product_name, rating, review_text, country, created_at） |
| 输出 | `ReviewAnalysis`（9 个字段：review_id, sentiment, issue_category, priority, responsible_team, summary_zh, suggested_action_zh, confidence, needs_human_review） |
| 调用 workflow.py | 是 → `analyze_review(review)` → `client.analyze_review()` → `apply_guardrails()` |
| 是否走 mock | 取决于环境变量和 API key |
| **缺失字段** | `evidence`、`is_mock`、`processing_time_ms` |
| 状态 | ✅ 正常工作 |

### POST /api/v1/analyze_batch

| 属性 | 说明 |
|------|------|
| 输入 | `{"reviews": [ReviewInput, ...]}` |
| 输出 | `{"results": [ReviewAnalysis, ...], "total": int, "needs_human_review_count": int}` |
| 调用 workflow.py | 是 → `analyze_batch_request(request)` → `analyze_reviews_batch()` → 逐条 `analyze_review()` |
| 是否走 mock | 同上 |
| **缺失字段** | `is_mock`、`processing_time_ms`、`error_count` |
| 状态 | ✅ 正常工作 |

---

## 5. 当前 n8n 相关文件

### 5.1 n8n/workflow_design.md — 完整性评估

| 维度 | 评分 | 说明 |
|------|------|------|
| 业务目标说明 | ⭐⭐⭐⭐⭐ | 6 个业务目标清晰，Why 解释到位 |
| 先决条件 | ⭐⭐⭐⭐⭐ | FastAPI 启动、健康检查、环境变量全覆盖 |
| 节点设计 | ⭐⭐⭐⭐ | 7 个节点设计（含可选），每个有详细配置表 |
| Code Node 示例 | ⭐⭐⭐⭐⭐ | 3 个完整 JavaScript 代码块，可直接复制使用 |
| 错误处理策略 | ⭐⭐⭐⭐⭐ | 8 种失败模式 + Mermaid 路由图 + 6 条生产原则 |
| 面试话术 | ⭐⭐⭐⭐⭐ | 完整 2 分钟中文脚本 |
| 未来扩展 | ⭐⭐⭐⭐⭐ | 4 个 Phase 的详细路线图 |
| 模板兼容性 | ⭐⭐⭐ | 承认 JSON 模板可能因版本不兼容导入失败 |

**结论：** 设计文档质量极高，**但 JSON 模板与设计文档之间存在巨大落差**。

### 5.2 n8n/review_workflow_template.json — 可导入性评估

| 属性 | 值 |
|------|-----|
| 节点数 | 5（Manual Trigger → Code → HTTP → Code → NoOp） |
| 是否包含错误处理节点 | ❌ 无 IF 节点、无错误分支 |
| 是否包含 Loop 节点 | ❌ 无 SplitInBatches |
| 是否包含 Feishu 节点 | ❌ 无 |
| 是否包含 Validate/Check 节点 | ❌ 无 |
| 是否包含 Schedule Trigger | ❌ 使用 Manual Trigger |
| 是否有 secrets | ✅ 无（URL 是 localhost，无 API key） |
| 是否可导入 | ⚠️ 取决于 n8n 版本 |
| 是否像生产流程 | ❌ **更像 Demo** |

### 5.3 当前 Workflow 是 Demo 还是生产

**结论：Demo 级别。** 以下是判断依据：

| 特征 | Demo | 生产 | 当前 |
|------|------|------|------|
| 数据来源 | 硬编码 Code Node | 数据库/API/CSV | **硬编码** |
| 错误处理 | 无/基本 | IF 分支 + 重试 + 死信队列 | **无** |
| 通知 | 无/console.log | Feishu/Slack/Email | **无** |
| 调度 | Manual Trigger | Schedule Trigger (Cron) | **Manual** |
| n8n 侧结果校验 | 无 | 检查 statusCode + 字段完整性 | **无** |
| 幂等性 | 无 | review_id 去重 | **无** |

### 5.4 当前缺少的生产节点

| 缺失节点 | 用途 | 优先级 |
|----------|------|--------|
| **IF 节点（HTTP 响应检查）** | 检查 statusCode != 200 → 错误分支 | 🔴 高 |
| **IF 节点（needs_human_review 检查）** | needs_human_review=true → 高优先级通知分支 | 🔴 高 |
| **SplitInBatches** | 大批量评论分批处理 | 🟡 中 |
| **Schedule Trigger** | 替代 Manual Trigger 做定时触发 | 🟡 中 |
| **Feishu HTTP Request** | 发送报告/告警到飞书群 | 🟡 中 |
| **Validate JSON 节点** | 校验 HTTP 响应是否包含全部必要字段 | 🟢 低 |
| **Error Output / 死信队列** | 失败 case 写到本地文件或 DB | 🟢 低 |

---

## 6. 当前测试覆盖了什么

### 测试统计

```
test_basic.py         : 9 tests   (2 failed — model 名称不匹配)
test_schema.py        : 15 tests  (全部通过)
test_workflow.py      : 16 tests  (全部通过)
test_api.py           : 26 tests  (全部通过)
test_report.py        : 20 tests  (全部通过)
test_guardrails.py    : 21 tests  (全部通过)
test_error_logging.py : 11 tests  (全部通过)
─────────────────────────────────
总计: 117 tests, 115 passed, 2 failed
```

### 各测试文件覆盖内容

| 测试文件 | 覆盖内容 | 依赖 DeepSeek API |
|----------|----------|-------------------|
| `test_basic.py` | 包导入、schema 实例化、config 默认值、LLM client mock 模式、workflow 函数可调用性、report 生成、health endpoint | ❌ 否 |
| `test_schema.py` | ReviewInput 校验（rating 范围、空文本）、ReviewAnalysis 默认值/confidence 范围/全字段、Batch 模型（空列表拒绝、结果顺序） | ❌ 否 |
| `test_workflow.py` | Mock 模式下 analyze_review 返回类型、低分触发人工复核、关键词检测（battery/logistics）、guardrails 管道集成、批量处理保序 | ❌ 否（全部 mock） |
| `test_api.py` | Health 端点 200/字段/schema、Analyze 端点 200/required fields/confidence 范围/bool 类型/高/低分 sentiment/422 各种场景、Batch 端点 200/total/results/needs_human_review_count/顺序/空列表 422/单条、安全测试（无 API key 泄露、无 traceback） | ❌ 否（全部 mock） |
| `test_report.py` | 空结果、总计数、negative count、human review count、Markdown 格式、自定义标题、无 API key 泄露、类别分布、团队分布、负面评论区、人工复核区、规则说明、置信度统计、优先级分布、error log 引用、全部需复核、error log entry 格式 | ❌ 否 |
| `test_guardrails.py` | 4 条规则独立测试（低置信度/矛盾/other+低分/空摘要）+ 自定义 threshold + 组合场景 + 不可变性 | ❌ 否（纯确定性规则） |
| `test_error_logging.py` | log_error_case 创建文件/写 JSONL/必填字段/raw_output 截断/API key 脱敏/写失败不抛异常、_sanitise_output Bearer Token 脱敏/API key 脱敏/无害字段保留/空字符串/非 JSON 文本 | ❌ 否 |

### 关键发现

1. **所有 117 个测试都在 mock 模式下运行**——没有测试验证真实 LLM 输出格式或 API 调用路径
2. **2 个失败测试**是因为 `.env` 文件中的 `DEEPSEEK_MODEL=deepseek-v4-pro` 与测试中硬编码的 `"deepseek-v4-flash"` 不匹配
3. **缺少的测试类型：**
   - Real API 调用的集成测试（需要 API key）
   - `_extract_json` 对异常 LLM 输出的容错测试
   - n8n workflow JSON 格式校验测试
   - `_call_api_with_retry` 错误分类的单元测试
   - 输出中 `is_mock` 标记的测试（当前不存在此字段）

---

## 7. 最影响面试可信度的 10 个问题

### Issue #1：默认 Mock，无感知切换
- **优先级：** 🔴 P0 — 最高
- **问题描述：** 无 API key 时自动静默切换到 mock 模式。用户跑 `python scripts/run_batch.py`（未加 --mock），看到输出以为调了 DeepSeek，实际跑的是关键词规则。
- **为何影响面试：** 面试官问"这里面哪些结果是 LLM 生成的？"你无法回答，因为**输出中没有 is_mock 标记**。如果面试官发现输出是模板字符串而非自然语言，信任瞬间崩塌。
- **建议改法：**
  1. API 响应和 JSON 输出中增加 `is_mock: bool` 字段
  2. 无 API key 时 CLI 触发性停止并提示，不再静默切换
  3. 报告的生成时间旁增加 `（Mock 模式）` 或 `（DeepSeek 实时分析）` 标识
- **对应 V2 里程碑：** V2-M1 (Schema) + V2-M2 (Real API)

### Issue #2：输出是模板字符串，不像 LLM 生成
- **优先级：** 🔴 P0 — 最高
- **问题描述：** `summary_zh` 使用 `f"用户反馈{category_name}问题，评分{rating}。"`、`suggested_action_zh` 使用 `f"建议{team}团队查看该评论..."`。更严重的是，当 `team="unknown"` 时输出 `"建议unknown团队查看该评论"`——这在真实 LLM 输出中绝不会出现。
- **为何影响面试：** 面试官一眼就能看出这是规则生成而非 LLM 生成。"AI 应用工程师"的核心能力之一是 LLM 集成，如果连真实 LLM 输出都没展示，面试无意义。
- **建议改法：**
  1. V2 默认以真实 DeepSeek 调用为主
  2. Mock 模式也改进 summary_zh 和 suggested_action_zh 为自然语言（用更丰富的模板或小型 LLM）
  3. 确保 "unknown" 团队不会出现在对外的建议文案中
- **对应 V2 里程碑：** V2-M2 (Real LLM)

### Issue #3：数据样本太少，不够真实
- **优先级：** 🔴 P0 — 最高
- **问题描述：** `data/mock/sample_reviews.csv` 只有 10 条评论。评论内容虽然覆盖了多个平台和类别，但全部是英文、全部是电子产品、全部是手动构造的。
- **为何影响面试：** 面试官问"这个系统每天能处理多少条评论？评论来自哪些国家？哪些语言？"时，10 条数据无法支撑任何有意义的演示。跨境电商的关键特征是**多语言、多品类、多平台**。
- **建议改法：**
  1. 扩展到 30-50 条评论，覆盖 3+ 语言（英/德/日/法）、5+ 产品品类
  2. 从公开数据源（如 Amazon 公开评论页）或 Kaggle 电商评论数据集提取真实评论
  3. 增加边缘 case：极短评论、纯 emoji、非英语、矛盾评分、多问题混合
- **对应 V2 里程碑：** V2-M3 (Real Data)

### Issue #4：API 响应中缺少 evidence/推理依据
- **优先级：** 🟡 P1 — 高
- **问题描述：** `ReviewAnalysis` schema 只有 9 个字段，没有 `evidence` 或 `reasoning` 字段说明 LLM 为什么判断这条评论是 battery 而不是 product_quality。
- **为何影响面试：** 面试的核心问题之一是"如何减少幻觉"。如果模型只输出结论而不输出依据，面试官会问"你怎么知道模型不是瞎猜的？"evidence 字段是回答这个问题的关键。
- **建议改法：**
  1. Schema 增加 `evidence_zh: str` 字段
  2. Prompt 中要求模型输出判断依据（引用 review_text 中的关键词）
  3. 报告中展示 evidence 而非仅展示类别
- **对应 V2 里程碑：** V2-M1 (Schema)

### Issue #5：n8n 模板太简单，不像生产
- **优先级：** 🟡 P1 — 高
- **问题描述：** JSON 模板只有 5 个节点（Trigger → Code → HTTP → Code → NoOp）。没有错误分支、没有条件路由、没有通知节点、没有定时触发。打开 n8n 后执行一次，看到 3 条硬编码评论的分析结果——这跟用 curl 调 FastAPI 没有本质区别。
- **为何影响面试：** n8n 是这个项目的编排层，面试的重点是"AI + 业务自动化"。如果一个 Workflow 没有展示异常处理、条件路由、通知分发，面试官看不出编排的价值。
- **建议改法：**
  1. 增加 IF 节点：检查 HTTP statusCode != 200 → 错误分支
  2. 增加 IF 节点：needs_human_review=true → 飞书通知分支
  3. 增加 Code Node：格式化飞书消息卡片
  4. 增加 Schedule Trigger 节点（演示用但可切换回 Manual）
  5. 将 Feishu webhook URL 设为可配置变量
- **对应 V2 里程碑：** V2-M4 (n8n)

### Issue #6：README 的 Quick Start 引导用户跑 Mock
- **优先级：** 🟡 P1 — 高
- **问题描述：** README.md 第 70-71 行的 Quick Start 第 4 步是 `python scripts/run_batch.py --mock`。所有示例 curl 输出（第 150-162 行）标注 "Expected output (mock mode)"，但 mock 输出看起来太模板化。API 示例输出（第 300-307 行）展示的是理想化的 LLM 输出（`"用户反馈电池续航差且夜视模糊。"`、"建议产品团队检查该型号电池投诉率和夜视表现。"），但 mock 模式实际产出的却是 `"用户反馈电池相关问题，评分2。"`。
- **为何影响面试：** README 展示的"Expected output"与实际 mock 产出**不一致**。面试官如果按 README 的 curl 示例执行，得到的返回跟文档中的示例不同——这是面试中的红灯。
- **建议改法：**
  1. README 的示例输出必须与实际运行结果一致
  2. 区分 "Mock 模式输出" 和 "Real LLM 输出" 两个示例区
  3. Quick Start 建议先跑 real（如果有 API key），再展示 mock 作为 fallback
- **对应 V2 里程碑：** V2-M5 (Interview Packaging)

### Issue #7：Error Log 被 Guardrail 噪声污染
- **优先级：** 🟡 P1 — 高
- **问题描述：** `error_cases.jsonl` 有 170 行，但 90%+ 是 `GUARDRAIL_TRIGGERED` 且仅包含 `high_priority_noted` 或 `other_category_low_rating`。这些不是真正的"错误"，而是 guardrail 的正常触发。真正的 API 失败、JSON 解析失败被淹没在噪声中。另外，**测试运行时 guardrails 测试也会写入 error log**，导致 log 混合了测试数据和生产数据。
- **为何影响面试：** 面试官看了 error log 会困惑——"为什么有 170 条错误？这个系统这么不稳定吗？"如果解释不清楚，反而暴露了日志设计的缺陷。
- **建议改法：**
  1. 分离日志：`guardrail_events.jsonl` vs `error_cases.jsonl`
  2. Guardrail 只在 `needs_human_review=True` **且**非 low_confidence 非 high_priority_noted 时才写 error log
  3. high_priority_noted 改为 debug 级别日志而非 error log
  4. 测试运行前清空或使用临时 error log 路径（已在 test_error_logging.py 中实现）
- **对应 V2 里程碑：** V2-M5 (Guardrails)

### Issue #8：Schema 缺乏枚举校验
- **优先级：** 🟢 P2 — 中
- **问题描述：** `sentiment`、`issue_category`、`priority`、`responsible_team` 在 schema 中定义为 `str` 类型，虽然在 Field description 中列出了允许值，但**没有用 Pydantic 的 Literal 或 AfterValidator 做枚举校验**。这意味着 LLM 返回 `"sentiment": "angry"` 或 `"issue_category": "shipping_problem"` 时，Pydantic 不会报错。
- **为何影响面试：** "你如何保证 LLM 输出的 schema 合规？"——不能只说"Pydantic 验证"，因为当前实现**实际上不验证枚举值**。面试官如果细看 schema 定义就会发现这个漏洞。
- **建议改法：**
  1. 使用 `Literal["logistics", "product_quality", ...]` 替代 `str`
  2. 或者使用 Pydantic `AfterValidator` + 一个 `validate_enum` 函数
  3. 测试中增加"非法枚举值被拒绝"的 case
- **对应 V2 里程碑：** V2-M1 (Schema)

### Issue #9：测试全部 Mock，无真实 LLM 集成测试
- **优先级：** 🟢 P2 — 中
- **问题描述：** 117 个测试没有一个调用真实 DeepSeek API（这是设计如此，CLAUDE.md 明确说 "Tests should avoid real API calls by default"）。但完全没有集成测试意味着**真实 API 调用路径从未被自动化验证过**。
- **为何影响面试：** 面试官可能问"你怎么测试 LLM 调用？"如果你回答"用 mock"，追问就是"那你如何保证真实 API 调用的 prompt 效果？"没有评估方法等于承认这部分未经测试。
- **建议改法：**
  1. 增加一个 `tests/test_integration.py`（需要 `DEEPSEEK_API_KEY` 环境变量才运行）
  2. 添加 `pytest.mark.skipif` 在没有 API key 时自动跳过
  3. 集成测试验证：真实 API 返回合法 JSON、字段类型正确、枚举值在允许范围内
- **对应 V2 里程碑：** V2-M5 (Testing)

### Issue #10：缺少演示录屏/截图
- **优先级：** 🟢 P2 — 中
- **问题描述：** `docs/demo_checklist.md` 非常详细，但缺少实际的可视化材料。`docs/` 目录下没有截图、没有录屏、没有 GIF。
- **为何影响面试：** 如果面试是远程进行、或者面试官想提前了解项目，一份有截图的 README 比纯文字 checklist 可信度高得多。面试现场如果 n8n 或 FastAPI 启动失败，有备用的截屏可以继续讲。
- **建议改法：**
  1. 在 `docs/demo_checklist.md` 中嵌入关键截图（FastAPI Swagger UI、n8n 执行成功、Report Markdown 渲染效果）
  2. 创建 `docs/screenshots/` 目录存放
  3. 准备 3-5 张核心截图作为 interview backup
- **对应 V2 里程碑：** V2-M5 (Interview Packaging)

---

## 8. 建议 V2 改造路线

### V2-M1：Schema / Config 升级

**目标：** 让输出像真实 AI 产品，可追溯、可区分

**改造项：**

| # | 改造 | 涉及文件 | 工作量 |
|---|------|----------|--------|
| 1.1 | Schema 增加 `evidence_zh: str` 字段 | schemas.py | 小 |
| 1.2 | Schema 增加 `is_mock: bool` 字段（默认 true） | schemas.py | 小 |
| 1.3 | Schema 增加 `processing_time_ms: float` 字段 | schemas.py | 小 |
| 1.4 | `sentiment`/`issue_category`/`priority`/`responsible_team` 使用 Literal 类型或 AfterValidator 做枚举校验 | schemas.py | 中 |
| 1.5 | BatchAnalysisResponse 增加 `is_mock` 和 `error_count` 字段 | schemas.py | 小 |
| 1.6 | Config 中删除硬编码 `low_rating_threshold`，改为从 env 读取 | config.py | 小 |
| 1.7 | 增加 `LOG_LEVEL` 和 `GUARDRAIL_LOG_MODE` 配置项 | config.py | 小 |

**验证标准：**
- 不合法枚举值（如 sentiment="angry"）在 schema 层被拒绝
- 测试更新以覆盖新字段
- `pytest -q` 全部通过

---

### V2-M2：真实 DeepSeek LLM 调用

**目标：** 让项目默认展示真实 LLM 能力，Mock 降级为 fallback

**改造项：**

| # | 改造 | 涉及文件 | 工作量 |
|---|------|----------|--------|
| 2.1 | 无 API key 时 CLI **停止并提示**，不再自动切换 mock（除非显式 --mock） | run_batch.py, llm_client.py | 小 |
| 2.2 | API 层：初始化时检测并记录当前模式（real/mock），全局可查询 | api.py, config.py | 小 |
| 2.3 | 所有 API 响应和 JSON 输出包含 `is_mock: bool` | api.py, workflow.py, run_batch.py | 小 |
| 2.4 | 改进 `_extract_json` 的日志：记录每次提取用了哪种策略（代码块/外括号/直接） | llm_client.py | 小 |
| 2.5 | Mock 模式也填充 `evidence_zh` 字段（如"依据：评论包含关键词'battery drain'"） | llm_client.py | 小 |
| 2.6 | 改进 mock summary_zh 为更自然的表述（不再用模板字符串 "评分X"） | llm_client.py | 中 |
| 2.7 | 确保 unknown 团队不会出现在 suggested_action_zh 的建议文案中 | llm_client.py | 小 |
| 2.8 | run_batch.py 增加 `--real` flag（显式声明使用真实 API） | run_batch.py | 小 |

**验证标准：**
- `python scripts/run_batch.py --mock` 产出结果的 `is_mock=true`
- `python scripts/run_batch.py --real`（有 API key）产出 `is_mock=false`、evidence_zh 非空
- 无 API key 不加 --mock 时 CLI 报错退出（不静默切换）
- 测试更新通过

---

### V2-M3：真实感评论数据样本

**目标：** 让评论数据看起来像真实跨境电商业务，而非手工玩具数据

**改造项：**

| # | 改造 | 涉及文件 | 工作量 |
|---|------|----------|--------|
| 3.1 | 扩展 CSV 从 10 条到 30-50 条 | data/mock/sample_reviews.csv | 中 |
| 3.2 | 覆盖多语言评论（英文 60% + 德语 15% + 日语 10% + 法语 10% + 西班牙语 5%） | data/mock/sample_reviews.csv | 中 |
| 3.3 | 覆盖多品类（消费电子 40% + 家居 20% + 服饰 15% + 运动 15% + 其他 10%） | data/mock/sample_reviews.csv | 中 |
| 3.4 | 增加边缘 case：极短评论（< 10 字）、emoji-only、矛盾评分、多问题混合、非英语长文 | data/mock/sample_reviews.csv | 中 |
| 3.5 | 从 Kaggle / Amazon 公开评论中提取真实评论文案（不包含 PII） | data/mock/sample_reviews.csv | 大 |
| 3.6 | Prompt 增加多语言处理说明 | prompts/review_classification_prompt.md | 小 |
| 3.7 | 创建 `data/real/` 目录（占位），说明真实数据源的接入方式 | 新增文件 | 小 |

**验证标准：**
- CSV 包含 30+ 条评论，3+ 语言
- `run_batch.py --mock` 产出结果覆盖所有 8 个类别
- 边缘 case 触发了 needs_human_review=true
- 报告展示了多语言评论的中文摘要

---

### V2-M4：API + n8n 生产流程优化

**目标：** 让 n8n workflow 看起来像生产级自动化，而非 curl 的图形化包装

**改造项：**

| # | 改造 | 涉及文件 | 工作量 |
|---|------|----------|--------|
| 4.1 | n8n 模板增加 IF 节点（statusCode != 200 → 错误分支 → 写错误日志） | n8n/review_workflow_template.json | 中 |
| 4.2 | n8n 模板增加 IF 节点（needs_human_review=true → 高优先级通知分支） | n8n/review_workflow_template.json | 中 |
| 4.3 | n8n 模板增加 Feishu HTTP Request 节点（发送消息卡片） | n8n/review_workflow_template.json | 中 |
| 4.4 | n8n 模板的 Code Node 支持从外部文件/API 读取评论数据（而非硬编码 3 条） | n8n/review_workflow_template.json | 小 |
| 4.5 | FastAPI 增加 `GET /api/v1/mode` 端点（返回当前 real/mock 状态） | api.py | 小 |
| 4.6 | n8n 模板增加健康检查节点（workflow 开始时检查 FastAPI 可用性） | n8n/review_workflow_template.json | 小 |
| 4.7 | 更新 workflow_design.md 以反映新节点 | n8n/workflow_design.md | 小 |
| 4.8 | Schema 增加 `error_count` 到 BatchAnalysisResponse | schemas.py | 小 |

**验证标准：**
- n8n 模板包含 8+ 个节点（vs 当前 5 个）
- IF 节点正确路由成功/失败/需复核三种路径
- Feishu 消息格式正确（用 webhook.site 或 mock URL 验证）
- FastAPI mode 端点正常返回

---

### V2-M5：测试完善 + 面试包装

**目标：** 让项目在面试中无漏洞可挑

**改造项：**

| # | 改造 | 涉及文件 | 工作量 |
|---|------|----------|--------|
| 5.1 | 修复 test_basic.py 中 2 个失败的 model 名称断言 | test_basic.py | 小 |
| 5.2 | 增加 Schema 枚举校验测试（非法值拒绝） | test_schema.py | 小 |
| 5.3 | 增加 `_extract_json` 边界 case 测试（嵌套 JSON、JSON 前后有文字、空响应等） | 新增或追加 | 中 |
| 5.4 | 增加集成测试 `tests/test_integration.py`（需要 API key，否则 skip） | 新增 | 中 |
| 5.5 | 分离 guardrail events 和 error cases 日志 | utils.py, workflow.py | 中 |
| 5.6 | 防止测试污染 error log（test run 使用临时路径） | conftest.py | 小 |
| 5.7 | 补充 docs/ 截图或录屏（FastAPI docs 页面、n8n 执行成功、Report 渲染） | docs/screenshots/ | 大 |
| 5.8 | 更新 README.md 所有示例输出与实际运行结果一致 | README.md | 中 |
| 5.9 | 更新 demo_checklist.md 增加 V2 新特性的演示步骤 | docs/demo_checklist.md | 中 |
| 5.10 | 创建 `.env.example` 增加所有新配置项 | .env.example | 小 |

**验证标准：**
- `pytest -q` 全部通过（117+ 个测试）
- `python scripts/run_batch.py --real` 跑出真实 LLM 结果
- `python scripts/run_batch.py --mock` 跑出改进后的 mock 结果
- README 中的每个 curl 示例的输出与用户实际运行一致
- n8n workflow 8+ 个节点导入成功并执行通过

---

## 总结

### 当前项目优势

1. **代码质量好：** 模块划分清晰、类型标注完整、异常处理全面、日志脱敏到位
2. **文档非常强：** interview_notes.md 的中文话术、workflow_design.md 的错误处理矩阵、demo_checklist 的分步引导——这些是面试中的巨大加分项
3. **Guardrails 设计扎实：** 6 层防线 + 4 条确定性规则 + 安全兜底——这是企业级 AI 应用的核心体现
4. **测试覆盖率高：** 117 个测试覆盖了 schema、workflow、api、report、guardrails、error logging

### 核心矛盾

**当前项目最大的矛盾是：文档和设计在讲"生产级 AI 应用"，但运行结果暴露的是"关键词规则 Demo"。**

具体表现为：
- README 展示的自然语言中文摘要 vs 实际输出的模板字符串
- interview_notes 讲 6 层防幻觉 vs Schema 实际不校验枚举值
- workflow_design 画了 8 个节点的生产流程 vs JSON 模板只有 5 个基础节点
- 强调 "DeepSeek LLM 分类" 但默认无 API key 时静默走 mock

### 建议优先级

| 顺序 | 里程碑 | 一句话目标 |
|------|--------|-----------|
| **1st** | V2-M1 (Schema/Config) | 让输出有 evidence、有 is_mock 标记、有枚举校验 |
| **2nd** | V2-M2 (Real LLM) | 让项目默认展示真实 LLM 能力，Mock 明确标识 |
| **3rd** | V2-M3 (Real Data) | 让评论数据像真实跨境电商，多语言多品类 |
| **4th** | V2-M4 (n8n) | 让 n8n 有 IF/错误路由/通知，像生产流程 |
| **5th** | V2-M5 (Tests + Polish) | 修复测试、补充集成测试、README 与产出一致 |

---

*报告由 Claude Code 在 V2-M0 审查阶段生成。未修改任何项目文件。*
