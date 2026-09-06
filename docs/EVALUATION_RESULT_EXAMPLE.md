# BEAM 与 Memora 测试能力及结果示例

> 本文用于说明两个数据集各个 case/persona 测试什么，以及统一记录 OpenClaw/openclaw-eval 实验结果。文中的 `<填写>` 都是占位符，不代表真实成绩。

## 一、先理解 case 与能力的关系

### BEAM：5个 case 是5个领域，不是5种能力

BEAM 当前固定抽样使用原始 case 索引 `0、4、8、12、16`。每个 case 都包含20道题，并且都覆盖完整的10种 `question_type`，即每种能力2题。

| 原始索引 | 领域 | QA数量 | 能力覆盖 |
|---:|---|---:|---|
| 0 | Coding | 20 | 10种能力，每种2题 |
| 4 | Math | 20 | 10种能力，每种2题 |
| 8 | Writing Assistant & Learning | 20 | 10种能力，每种2题 |
| 12 | Asking Recommendation | 20 | 10种能力，每种2题 |
| 16 | Lifestyle | 20 | 10种能力，每种2题 |
| 合计 | 5个领域 | 100 | 每种能力共10题 |

因此，不能把 Coding case 解释为只测试代码能力，也不能把 Recommendation case 解释为只测试推荐能力。领域决定对话内容，10种题型才是正式统计维度。

#### BEAM 的10种能力

| question_type | 主要测试内容 |
|---|---|
| `abstention` | 记忆中没有充分依据时，能否明确表示无法回答，而不是编造 |
| `contradiction_resolution` | 新旧信息冲突时，能否采用当前有效信息并排除过期信息 |
| `event_ordering` | 能否还原多个事件发生的先后顺序 |
| `information_extraction` | 能否从历史对话中准确提取明确事实 |
| `instruction_following` | 能否长期保持并执行用户先前给出的要求 |
| `knowledge_update` | 用户信息发生更新后，能否用新值替代旧值 |
| `multi_session_reasoning` | 能否联合多个 session 的信息完成推理 |
| `preference_following` | 能否根据长期偏好调整回答或建议 |
| `summarization` | 能否概括跨会话的重要内容且不遗漏关键点 |
| `temporal_reasoning` | 能否理解日期、持续时间、相对时间与时间约束 |

低成本3-case版选择索引 `0、8、16`，覆盖 Coding、Writing Assistant & Learning、Lifestyle，共60题；仍然是每种能力6题。

### Memora：3个 case 是3个 persona，每个都覆盖3类能力

Memora Weekly 当前选择3个 persona。每个 persona 有15道主问题，其中 Remembering、Reasoning、Recommending 各5题。

| persona | 领域特征 | sessions | Remembering | Reasoning | Recommending | QA合计 |
|---|---|---:|---:|---:|---:|---:|
| `software_engineer` | 软件开发、技术任务、项目状态 | 163 | 5 | 5 | 5 | 15 |
| `financial_analyst` | 金融分析、数据判断、工作安排 | 156 | 5 | 5 | 5 | 15 |
| `creative_designer` | 创意设计、偏好、项目与活动 | 147 | 5 | 5 | 5 | 15 |
| 合计 | 3个领域 | 466 | 15 | 15 | 15 | 45 |

#### Memora 的3种能力

| task_type | 主要测试内容 |
|---|---|
| `Remembering` | 直接召回仍然有效的历史事实、任务、事件或状态 |
| `Reasoning` | 整合多条长期记忆，得到不能由单条记录直接回答的结论 |
| `Recommending` | 根据用户长期偏好、约束和历史行为给出合适建议 |

Memora 还会从两个方向检查答案：

- `memory_presence`：应该记住的有效信息是否出现在回答中；
- `forgetting_absence`：已经删除、替换或失效的旧信息是否没有残留。

正式分数使用 FAMA，而不是 LoCoMo 的 EM/F1。Reasoning 题通常没有 `forgetting_absence`，此时逐题 FAMA 等于 Memory Presence Accuracy。

## 二、实验信息模板

| 项目 | 填写内容 |
|---|---|
| 实验名称 | `<填写>` |
| 运行日期 | `<填写>` |
| 数据集与版本 | `BEAM 100K 5-case / BEAM 100K 3-case / Memora Weekly 3-persona` |
| 固定样本索引 | `<填写>` |
| OpenClaw版本 | `<填写>` |
| openclaw-eval版本 | `<填写>` |
| memory backend | `<填写>` |
| embedding模型 | `<填写>` |
| chunk配置与top-k | `<填写>` |
| answer model | `<填写>` |
| judge model | `<填写>` |
| temperature | `<填写>` |
| 并发数 | `<填写>` |
| session隔离方式 | `<填写>` |
| 超时与重试策略 | `<填写>` |

## 三、数据完整性检查

| 数据配置 | 预期规模 | 实际规模 | 状态 |
|---|---:|---:|---|
| BEAM 5-case | 5 cases / 100 QA / 10类能力各10题 | `<填写>` | `<通过/失败>` |
| BEAM 3-case | 3 cases / 60 QA / 10类能力各6题 | `<填写>` | `<通过/失败>` |
| Memora 3-persona | 3 personas / 466 sessions / 45 QA | `<填写>` | `<通过/失败>` |
| Memora rubric | 148 memory_presence / 73 forgetting_absence | `<填写>` | `<通过/失败>` |

## 四、BEAM 测试结果示例

> BEAM 必须按 rubric criterion 评分。建议同时报告 overall rubric score、binary pass rate 和10类能力分数。

### 总体结果

| 指标 | 结果 |
|---|---:|
| 完成题数 | `<填写>` |
| 成功率 | `<填写>%` |
| Overall rubric score | `<填写>` |
| Binary pass rate | `<填写>%` |
| 平均回答延迟 | `<填写>秒` |
| Input tokens | `<填写>` |
| Output tokens | `<填写>` |
| 超时/错误数 | `<填写>` |

### 按能力分项

| question_type | 题数 | 平均rubric分 | 通过率 |
|---|---:|---:|---:|
| abstention | `<填写>` | `<填写>` | `<填写>%` |
| contradiction_resolution | `<填写>` | `<填写>` | `<填写>%` |
| event_ordering | `<填写>` | `<填写>` | `<填写>%` |
| information_extraction | `<填写>` | `<填写>` | `<填写>%` |
| instruction_following | `<填写>` | `<填写>` | `<填写>%` |
| knowledge_update | `<填写>` | `<填写>` | `<填写>%` |
| multi_session_reasoning | `<填写>` | `<填写>` | `<填写>%` |
| preference_following | `<填写>` | `<填写>` | `<填写>%` |
| summarization | `<填写>` | `<填写>` | `<填写>%` |
| temporal_reasoning | `<填写>` | `<填写>` | `<填写>%` |

### 按 case/领域分项

| case | 领域 | 题数 | 平均rubric分 | 通过率 |
|---:|---|---:|---:|---:|
| 0 | Coding | `<填写>` | `<填写>` | `<填写>%` |
| 4 | Math | `<填写>` | `<填写>` | `<填写>%` |
| 8 | Writing Assistant & Learning | `<填写>` | `<填写>` | `<填写>%` |
| 12 | Asking Recommendation | `<填写>` | `<填写>` | `<填写>%` |
| 16 | Lifestyle | `<填写>` | `<填写>` | `<填写>%` |

## 五、Memora 测试结果示例

> Memora 使用逐题 FAMA，再对任务和 persona 求平均。必须同时报告 MPA 与 FAA，才能区分“没记住”和“旧信息残留”。

### 总体结果

| 指标 | 结果 |
|---|---:|
| 完成题数 | `<填写>/45` |
| Overall FAMA | `<填写>` |
| Memory Presence Accuracy（MPA） | `<填写>` |
| Forgetting Absence Accuracy（FAA） | `<填写>` |
| 平均回答延迟 | `<填写>秒` |
| Input tokens | `<填写>` |
| Output tokens | `<填写>` |
| 超时/错误数 | `<填写>` |

### 按任务能力分项

| task_type | 题数 | FAMA | MPA | FAA |
|---|---:|---:|---:|---:|
| Remembering | 15 | `<填写>` | `<填写>` | `<填写>` |
| Reasoning | 15 | `<填写>` | `<填写>` | `通常不适用` |
| Recommending | 15 | `<填写>` | `<填写>` | `<填写>` |

### 按 persona 分项

| persona | sessions | 题数 | FAMA | MPA | FAA |
|---|---:|---:|---:|---:|---:|
| software_engineer | 163 | 15 | `<填写>` | `<填写>` | `<填写>` |
| financial_analyst | 156 | 15 | `<填写>` | `<填写>` | `<填写>` |
| creative_designer | 147 | 15 | `<填写>` | `<填写>` | `<填写>` |

## 六、失败样例记录

| 字段 | 内容 |
|---|---|
| dataset | `<BEAM/Memora>` |
| sample/persona | `<填写>` |
| question_id | `<填写>` |
| question_type | `<填写>` |
| 问题 | `<填写>` |
| 模型回答 | `<填写>` |
| 参考答案或rubric | `<填写>` |
| 得分 | `<填写>` |
| 错误类型 | `<未召回/旧信息残留/冲突处理错误/时间推理错误/编造/超时/其他>` |
| 原因分析 | `<填写>` |

## 七、结果解读规则

1. BEAM 的 case 是领域切片，正式能力结论必须依据10种 `question_type` 分项。
2. Memora 的 persona 是角色/领域切片，正式能力结论必须依据 Remembering、Reasoning、Recommending 分项。
3. BEAM 不能用普通 LoCoMo F1 代替 rubric score；Memora 不能用普通准确率代替 FAMA。
4. 报告平均分时必须同时写题数、失败数和数据索引，避免不同抽样规模之间直接误比。
5. answer model、judge model、memory backend 或索引策略改变后，应视为新的实验配置。

## 八、建议的结论写法

> 在 `<数据配置>` 上，`<memory backend>` 的总体得分为 `<填写>`。BEAM 的优势能力是 `<填写>`，薄弱能力是 `<填写>`；Memora 的 Remembering、Reasoning、Recommending FAMA 分别为 `<填写>`、`<填写>`、`<填写>`。错误主要来自 `<填写>`。本结果使用 `<answer model>` 与 `<judge model>`，共完成 `<填写>` 道题，失败 `<填写>` 道。

这段结论只应在全部占位符替换为真实运行结果后使用。
