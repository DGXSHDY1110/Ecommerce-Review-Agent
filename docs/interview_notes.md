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

### 如何防止幻觉 (How to Reduce Hallucination)

> 面试标准回答（中文）：

"消除幻觉不是一个技术，而是一层一层的防线。我们这个项目从六个层面控制幻觉：

**第一层：Prompt 限制。** 系统 Prompt 明确要求 LLM「只基于 review_text 判断，不允许编造外部事实，不允许编造平台统计数据，不允许编造用户没提到的问题」。这相当于给模型划定了一个认知边界。

**第二层：JSON-only 输出。** Prompt 要求只输出 JSON，不允许输出解释或自由文本。这不是为了省解析，而是因为模型一旦开始「解释」，就容易过度脑补。JSON 是结构化约束，字段名固定、值域有限，模型很难在 JSON 里编造长篇谎言。

**第三层：Pydantic Schema 校验。** 即使 LLM 输出了 JSON，我们也用 Pydantic 验证每一个字段的类型、取值范围。如果 schema 对不上——比如 issue_category 不在枚举列表里——我们直接丢弃，触发重试。

**第四层：置信度阈值 + 人工复核。** confidence < 0.6 的结果，不管内容看起来多合理，都标记 needs_human_review=true。低置信度的本质就是「模型自己都不确定」，这种结果不应该自动进入业务系统。

**第五层：业务一致性规则。** 评分 1-2 但情绪不是 negative → 明显矛盾 → 转人工。issue_category=other 且评分 <= 2 → 模型无法归类但又是低分 → 转人工。中文摘要为空 → 模型没有产生有效输出 → 转人工。这些规则是确定性的，不依赖 LLM。

**第六层：失败日志沉淀。** error_cases.jsonl 记录每一次解析失败、校验失败、API 超时、guardrail 触发。这些日志可以用来复盘——是 Prompt 问题、模型问题、还是输入数据问题。这是从 Demo 到生产系统的关键差别。

后续如果接 RAG，可以让模型在分类时参考标准 SOP 文档和产品 FAQ，进一步缩小「瞎猜」的空间。但核心原则不变：模型只做它该做的判断，所有不确定的交给人工。"

---

### 如何保证 LLM 输出稳定 (How to Keep JSON Output Stable)

> 面试标准回答（中文）：

"LLM 本质上是概率模型，同一段 Prompt 跑两次可能输出不一样。这在业务系统里是不可接受的——你不能今天告诉运营团队这条评论是 'battery'，明天同样的评论变成 'product_quality'。

我们的策略是「限制自由、增加约束」：

**第一，严格 JSON 输出。** Prompt 里写了 'You MUST respond with ONLY a single valid JSON object. Do NOT output markdown code fences. Do NOT output any explanation, preamble, or commentary.' 这直接限制了模型的输出空间。输出空间越小，稳定性越高。

**第二，Few-shot 示例锚定。** Prompt 里包含 4 个 Few-shot 示例，覆盖了「明确负面」「混合评价（物流差但产品好）」「信息不足」「评分文字矛盾」四类典型场景。这些示例给模型提供了输出风格的「锚」，降低随机性。

**第三，多层 JSON 提取。** LLM 有时候还是会加代码块标记 ` ```json ... ``` `，或者在 JSON 前后加说明文字。我们的 `_extract_json` 函数做了三层兜底：先尝试提取代码块内容 → 再尝试找到最外层 `{...}` → 最后尝试直接解析全文。这比直接 `json.loads(response)` 的鲁棒性高很多。

**第四，自动重试。** 如果 JSON 解析失败，我们会以更严格的指令重试一次。很多情况下第二次就能成功。重试次数通过 `RETRY_MAX_ATTEMPTS` 配置，默认 2 次（总共 3 次尝试）。

**第五，Safe Fallback。** 如果所有重试都失败怎么办？不能把空结果或乱码写入业务系统。我们用 `_safe_fallback` 生成一个安全的兜底结果：issue_category=other, confidence=0.0, needs_human_review=true。运营团队看到这个就知道需要手动处理。

**第六，Pydantic 强校验。** ReviewAnalysis schema 里每一个字段都有类型、范围、默认值的约束。confidence 必须是 float 且 0.0-1.0，sentiment 必须是 positive/neutral/negative 之一。Schema 不通过 → 重试 → 失败 → fallback。

**第七，Mock 模式。** 开发阶段和面试演示用 Mock 模式，关键字规则分类，完全不调 API。输出虽然不如真模型精准，但绝对稳定——同样的输入永远得到同样的输出。这在调试和测试时价值很大。

总结一句话：不能完全相信 LLM 的自由文本输出。要在 LLM 外面包一层又一层的约束和校验——Prompt 约束、JSON 约束、Schema 约束、Guardrail 约束——把不可控的概率输出变成可控的确定性输出。"

---

### 如何处理 API 超时和失败 (How to Handle API Failures)

> 面试标准回答（中文）：

"外部 API 不可能 100% 可用。我们做了完整的失败处理链路：

**第一，Timeout 控制。** HTTP 请求设置了 `LLM_TIMEOUT_SECONDS`（默认 30 秒）。30 秒内没有响应就触发异常。不能让一个 slow request 把整个批量任务卡死。

**第二，分类重试策略。** 不是所有错误都重试。JSON 解析失败 → 重试（模型可能修正格式）。Timeout / 网络错误 → 重试（瞬时故障）。4xx 客户端错误（如 401 Unauthorized）→ 不重试（重试也没用，API key 不对）。5xx 服务端错误 → 重试。这个分类策略避免了无意义的等待。

**第三，Safe Fallback。** 重试全部耗尽后，不抛异常让整个流程崩溃。我们用 `_safe_fallback()` 返回一个安全兜底结果：issue_category=other, confidence=0.0, needs_human_review=true, summary_zh='AI 解析失败，已使用安全兜底结果'。下游节点可以继续处理，而不是卡死在一条评论上。

**第四，error_cases.jsonl。** 每一次 API 失败都会记录到 outputs/results/error_cases.jsonl，包含 timestamp、review_id、error_type、error_message、fallback_used、needs_human_review。这很重要——如果哪天发现大量 API_TIMEOUT，就知道该调大超时或换模型了。**不让工作流静默失败**。

**第五，needs_human_review 兜底。** 所有 fallback 结果的 needs_human_review 都是 true。运营团队扫一眼就知道哪些结果是「机器没处理、需要人工看」。

**第六，安全日志。** error_message 和 raw_output 在写入日志前会经过 `_sanitise_output` 处理：正则匹配并替换 Bearer Token、api_key 字段等。API key 绝对不会出现在日志文件里。这是生产系统的基本素养。

这条链路的核心思想是：**允许失败，但不能让失败扩散，不能让失败静默。**"

---

### 如何处理重复执行 (How to Handle Idempotency)

> 面试标准回答（中文）：

"工作流重复执行是一个生产环境很常见的问题。n8n 支持重试、手动触发、定时触发——如果一个 Schedule Trigger 每天 9 点跑一次，但又有人在 9:05 手动了，同一条评论可能被分析两次。

我们的处理策略：

**第一，review_id 作为幂等键。** 每条评论有唯一的 review_id。在下游节点（比如写飞书多维表格、数据库、发送通知）之前，先检查 review_id 是否已经处理过。如果存在且状态不是 '待处理'，就跳过。

**第二，增加 status 字段。** 我们的 JSON 结果可以（在生产版本中）加入 status 字段：pending → analyzed → reviewed → closed。同一个 review_id，只有 status=pending 时才触发新分析。

**第三，execution_id / run_id 标记。** 每次批量分析生成一个 run_id（时间戳或 UUID），写入每条结果的 metadata。这样即使同一条评论被处理了两次，也能追溯到是哪次运行产生的。

**第四，避免重复通知。** 在飞书通知节点前加 Check：同一 review_id 在同一天内只通知一次。n8n Code Node 可以维护一个简单的去重 Set。

**第五，MVP 阶段的简单做法。** 当前版本结果写在本地 JSON 文件里，review_id 是 key，再次运行会覆盖。所以重复执行不会产生重复数据。但汇报里统计的是单次运行结果，所以报告是准确的。

核心原则：**幂等不是「不会重复」而是「重复不会产生副作用」。** review_id + status 的组合足以保证这一点。"

---

### Workflow 和 Agent 的区别 (Workflow vs Agent)

> 面试标准回答（中文）：

"这是一个面试高频问题，也是在项目设计阶段就要想清楚的选择。

**Workflow 是固定流程。** 节点和连线是预定义的——先做什么、后做什么、分支条件是什么——每一步都确定。n8n 就是典型的 Workflow 引擎。它的优点是稳定、可控、可审计、可监控。成本可预测。缺点是灵活性差——流程变了就要改节点。

**Agent 是动态决策。** Agent 自己决定调用哪个工具、什么时候停、要不要回溯。灵活性高，适合多步推理、多工具协作的不确定场景。但缺点是更难控制——可能循环调用、可能选错工具、token 消耗不可预测、输出质量波动大。

**本项目第一版是 Agentic Workflow。** 什么叫 Agentic Workflow？就是整体流程是固定的 Workflow（n8n 编排触发→数据准备→API 调用→结果聚合→报告输出），但在关键节点中嵌入了 LLM 的智能判断。LLM 在分类节点做出了「理解评论内容 → 判断情绪 → 分类问题 → 生成中文摘要和建议」的智能行为。这不是简单的 if-else，而是真正的语义理解。但它被约束在一个固定的 JSON 输出格式里，不会自由决定「下一步做什么」。

**为什么这个选择是对的？** 评论分类是一个标准化、高频率、可重复的任务。你不需要 Agent 在分类时去查天气、调用翻译 API、或者去搜索引擎搜产品参数。过度灵活反而带来不稳定性。Workflow + LLM 在成本、稳定性、可控性之间达到了最好的平衡。

**n8n 负责固定编排。** 触发、数据准备、HTTP 调用、结果聚合、报告输出——这些都是确定性步骤，不需要 LLM 参与。

**LLM 在分类节点里做智能判断。** 情绪分析、类别判断、优先级判断、中文摘要——这些是 LLM 真正强的地方。但它被严格限制在一个 JSON 输出框里，不能往外跳。

**后续如果加入更复杂的场景——** 比如 RAG 检索 SOP 知识库来判断建议动作、工具路由让模型自己决定要不要查产品数据库、多步推理判断是否需要升级为紧急工单——那就可以在分类节点内部升级为更完整的 Agent 模式。但这个 Agent 仍然是 n8n Workflow 中的一个节点，不失控。

一句话总结：**Workflow 是骨架，LLM 是大脑，n8n 是神经系统。分工明确，各司其职。**"

---

### 为什么这个项目适合 AI 应用工程岗位 (Why This Project Demonstrates AI Application Engineering)

> 面试标准回答（中文）：

"面试官可能问：「你这个项目跟模型训练有什么关系？跟 NLP 研究有什么关系？」答案是：没什么关系，因为 AI 应用工程跟模型训练是完全不同的岗位。

**AI 应用工程的核心不是训练模型，而是用工程化手段把 AI 能力接入业务流程。**

我这个项目展示了 AI 应用工程岗需要的 8 项核心能力：

**第一，业务流程拆解。** 跨境电商评论监控的原始流程是：客服每天打开后台 → 看几十条评论 → 判断是不是差评 → 判断是什么问题 → 通知对应团队 → 写日报。我把这个流程拆成了「数据采集→AI 分类→Schema 校验→Guardrails 过滤→报告生成→通知分发」六个标准化步骤。不是拍脑袋设计，是从业务中来。

**第二，LLM API 接入。** 不是「用 ChatGPT 写一个聊天机器人」。而是通过 OpenAI-compatible API 接入 DeepSeek，做了 prompt engineering、temperature 控制、JSON 提取、重试、fallback 全套工程封装。

**第三，Prompt Engineering。** Prompt 不是一句话，而是一个完整的规范文档（review_classification_prompt.md）：输出格式定义、字段定义、类别定义、优先级定义、反幻觉规则、置信度评分标准、矛盾检测规则、4 个 Few-shot 示例。这是工程化的 Prompt，不是临时敲的。

**第四，FastAPI 服务封装。** AI 能力不能只在 Jupyter Notebook 里跑。我把它封装成 REST API 服务，有标准输入输出、有 OpenAPI 文档、有健康检查、有批量接口。

**第五，结构化输出。** Pydantic Schema 定义了 ReviewInput 和 ReviewAnalysis，确保字段类型、取值范围、默认值都是明确的。这不是「让模型输出 JSON」就完了，而是「让模型输出符合业务 Schema 的 JSON，对不上就重试，再对不上就 fallback」。

**第六，n8n 工作流编排。** 不是自己写一个 Python 脚本来调度。n8n 是企业级工作流引擎——触发、数据流、异常路由、通知分发——这些不是 AI 的活，是编排引擎的活。n8n Code Node 还能写 JavaScript 做自定义处理，灵活性远高于纯无代码平台。

**第七，异常处理和 Guardrails。** 这个项目不是「正常情况下能跑」就完了。LLM API 超时怎么办？JSON 解析失败怎么办？输出矛盾怎么办？低置信度怎么办？每一个异常路径都有明确的处置逻辑。这是企业级应用跟 Demo 的本质区别。

**第八，后续可扩展性。** 虽然当前是 MVP，但架构已经预埋了扩展点：接 Amazon SP-API 拿真实评论、接 Shopify Admin API、接飞书 Webhook 发通知、接飞书多维表格做人工复核状态管理、接 RAG 知识库做 SOP 匹配。不是说大话，而是每一层的接口都是解耦的——换个 LLM Provider 不用改 n8n，换个数据源不用改 FastAPI。

一句话总结：**我不是在展示「模型有多强」，而是在展示「我能把 AI 稳定、可控、可扩展地接入真实业务流程」。这就是 AI 应用工程岗的价值。**"

---

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
