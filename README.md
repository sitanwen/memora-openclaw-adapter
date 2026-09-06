# Memora → OpenClaw Eval 适配项目

本项目把 [Memora](https://github.com/geniesinc/Memora) 长期记忆数据集适配到
OpenClaw / `openclaw-eval`，并提供与现有 LoCoMo、LongMemEval runner 兼容的
LoCoMo-like JSON。

仓库已经包含：

- 官方 Weekly 数据的 3 个固定 persona；
- 466 个会话、45 道主问题；
- 148 条 `memory_presence` 与 73 条 `forgetting_absence` 评分条件；
- 转换、校验、workspace/suite 生成、结果合并、多 judge、FAMA 聚合脚本；
- 中文注释、示例和自动测试。

## 为什么选择这 3 个 persona

固定选择：

- `software_engineer`：163 sessions；
- `financial_analyst`：156 sessions；
- `creative_designer`：147 sessions。

三者覆盖技术、金融和创意领域。每个 persona 都有 15 道题：Remembering、Reasoning、
Recommending 各 5 道，因此总计 45 道，适合先做一轮成本可控但任务类型完整的测试。

## 最重要的评分注意事项

**不能继续使用 LoCoMo 的 EM/F1 或普通问答 judge。**

Memora 没有为每道主问题提供单一自由文本标准答案。它提供多个 yes/no 子问题：

- `memory_presence`：回答应正确使用仍然有效的记忆；
- `forgetting_absence`：回答不应残留已经删除或被更新的信息。

官方逐题公式为：

```text
FAMA = max(0, MPA - λ × (1 - FAA))

MPA = memory_presence 正确数 / memory_presence 总数
FAA = forgetting_absence 正确数 / forgetting_absence 总数
λ   = forgetting_absence 总数 / 两类子问题总数
```

任务分数是该任务下“逐题 FAMA”的平均值乘以 100。Reasoning 题通常没有
`forgetting_absence`，此时 FAMA 等于 MPA。

## 项目结构

```text
memora-openclaw-adapter/
├─ configs/sample_personas.json
├─ data/
│  ├─ raw/weekly/<persona>/
│  │  ├─ conversations/session_NNNN.json
│  │  └─ evaluation_questions_<persona>.json
│  ├─ converted/memora_weekly_3personas_locomo.json
│  ├─ CHECKSUMS.sha256
│  ├─ DATA_LICENSE.md
│  └─ MEMORA_LICENSE
├─ scripts/
│  ├─ download_memora.py
│  ├─ convert_memora_to_locomo.py
│  ├─ validate_conversion.py
│  ├─ prepare_openclaw_eval.py
│  ├─ merge_openclaw_results.py
│  ├─ judge_memora_answers.py
│  ├─ aggregate_fama_scores.py
│  └─ generate_checksums.py
├─ examples/scored_answers.example.jsonl
├─ tests/test_converter.py
└─ pyproject.toml
```

## 快速开始

```bash
git clone git@github.com:sitanwen/memora-openclaw-adapter.git
cd memora-openclaw-adapter
uv sync --extra dev

uv run python scripts/validate_conversion.py \
  data/converted/memora_weekly_3personas_locomo.json
```

期望输出：

```text
校验通过：3 personas，466 sessions，45 QA；memory_presence=148，forgetting_absence=73
```

仓库中的原始数据和转换结果已经可用；不需要为了第一次运行而重新下载或转换。

## 路线 A：复用现有 LoCoMo / LongMemEval runner

直接把输入切换为：

```text
data/converted/memora_weekly_3personas_locomo.json
```

一个 sample 对应一个 persona 的完整 Weekly 记忆：

```python
for sample in dataset:
    # 一个 persona 只写入并建立一次记忆索引
    prepare_memory(sample["conversation"])

    # 15 道题复用同一份只读记忆，每道题使用新的 agent session
    for qa in sample["qa"]:
        response = ask_openclaw(qa["question"])
        save_response(
            sample_id=sample["sample_id"],
            question_id=qa["question_id"],
            question_type=qa["question_type"],
            response=response,
            evaluation_questions=qa["evaluation"]["evaluation_questions"],
        )
```

转换后的一条 QA 形如：

```json
{
  "question_id": "activity_todos_163",
  "question": "What tasks remain on my todo list this week?",
  "answer": "",
  "category": 1,
  "question_type": "remembering",
  "task_type": "Remembering",
  "evaluation": {
    "evaluation_questions": [
      {
        "evaluation_question": "Does the response mention the task: Optimize database queries?",
        "expected_answer": "yes",
        "evaluation_type": "memory_presence"
      },
      {
        "evaluation_question": "Does the response mention the deleted task: Buy groceries?",
        "expected_answer": "no",
        "evaluation_type": "forgetting_absence"
      }
    ]
  }
}
```

`category` 只是为 LoCoMo-like runner 提供数字兼容字段：1=Remembering、2=Reasoning、
3=Recommending。正式统计必须使用 `question_type` 和 FAMA。

## 路线 B：生成原生 openclaw-eval 输入

```bash
uv run python scripts/prepare_openclaw_eval.py \
  data/converted/memora_weekly_3personas_locomo.json
```

默认生成：

```text
generated/
├─ workspaces/<sample-id>/memory/memora/session_NNNN.md
├─ suites/<sample-id>.jsonl
├─ judging/<sample-id>.jsonl
├─ manifest.json
└─ run_commands.ps1
```

suite 只包含给被测 OpenClaw 的问题：

```json
{
  "id": "memora-weekly-software-engineer-q00",
  "prompt": "What tasks remain on my todo list this week?",
  "tags": ["memora", "weekly", "software_engineer", "remembering"],
  "checks": [{"type": "manual"}]
}
```

gold rubric 单独保存在 `generated/judging/*.jsonl`，不会进入 prompt，也不会写进
workspace，避免把正确记忆或待遗忘内容泄漏给 agent。

### 运行 OpenClaw

先复用你已有 LoCoMo / LongMemEval 的 memory backend 配置和显式建索引步骤，然后执行：

```powershell
.\generated\run_commands.ps1
```

三个 persona 使用三个独立 workspace，防止跨 persona 污染。同一 persona 的 15 道题
共享同一份静态记忆，但每题应创建新的 agent session，防止前一题回答泄漏到后一题。

不同版本的 OpenClaw 和 memory plugin 建索引命令不同，因此本项目不会硬编码某个
backend 命令。生成的 memory Markdown 可直接接入你现在已经可运行的索引流程。

## 合并、评分与聚合

### 1. 合并 OpenClaw 输出与 rubric

以 `software_engineer` 为例：

```bash
uv run python scripts/merge_openclaw_results.py \
  generated/runs/memora-weekly-software-engineer/results.json \
  generated/judging/memora-weekly-software-engineer.jsonl \
  -o generated/answers/memora-weekly-software-engineer.jsonl
```

合并脚本兼容 `results.json`、JSON 数组和 JSONL，并兼容常见 camelCase / snake_case
字段。它同时保留 latency、tokens、tool calls 和 read files。

### 2. 用官方协议进行 LLM-as-judge

先设置 OpenRouter key：

```powershell
$env:OPENROUTER_API_KEY = "你的key"
```

完整官方风格多 judge：

```bash
uv run python scripts/judge_memora_answers.py \
  generated/answers/memora-weekly-software-engineer.jsonl \
  -o generated/scored/memora-weekly-software-engineer.jsonl
```

默认 judge 与 Memora 官方发布代码一致：

- `openai/gpt-4.1`
- `anthropic/claude-haiku-4.5`
- `google/gemini-2.5-flash`

每个 rubric criterion 由三个 judge 独立回答 yes/no，再做多数投票。第一次可先跑低成本
冒烟测试：

```bash
uv run python scripts/judge_memora_answers.py \
  generated/answers/memora-weekly-software-engineer.jsonl \
  -o generated/scored/smoke.jsonl \
  --judge-model openai/gpt-4.1 \
  --limit 1
```

注意：45 道主问题共有 221 条 rubric；完整三 judge 会产生 663 次 judge 请求。

### 3. 聚合 FAMA

```bash
uv run python scripts/aggregate_fama_scores.py \
  generated/scored/memora-weekly-software-engineer.jsonl \
  -o generated/reports/software_engineer.json
```

若要一次统计三个 persona，可先把三个 scored JSONL 合并，再运行聚合脚本：

```powershell
Get-Content generated\scored\*.jsonl |
  Set-Content -Encoding utf8 generated\scored\all.jsonl

uv run python scripts/aggregate_fama_scores.py \
  generated/scored/all.jsonl \
  -o generated/reports/all.json
```

报告包含：

- overall FAMA；
- Remembering / Reasoning / Recommending 分项 FAMA；
- 每个 persona 的 FAMA；
- Memory Presence Accuracy（MPA）；
- Forgetting Absence Accuracy（FAA）；
- latency、input/output tokens、tool calls、read files。

可先用仓库示例验证聚合器：

```bash
uv run python scripts/aggregate_fama_scores.py \
  examples/scored_answers.example.jsonl \
  -o generated/example_report.json
```

## 重新下载与转换

仓库已经包含数据。需要从固定官方 commit 重建时：

```bash
uv run python scripts/download_memora.py --force

uv run python scripts/convert_memora_to_locomo.py \
  data/raw/weekly \
  --period weekly \
  --personas software_engineer financial_analyst creative_designer \
  -o data/converted/memora_weekly_3personas_locomo.json
```

下载来源和 commit 写在 `configs/sample_personas.json` 与 `data/raw/SOURCE.json`。

## 测试

```bash
uv run pytest -q
```

测试覆盖 persona 转换、45 QA 完整性、221 条 rubric、官方 FAMA 公式以及
openclaw-eval 结果字段兼容。

## 实验时还需记录

为了不同运行之间可比较，建议在最终报告中同时记录：

- OpenClaw 与 openclaw-eval 版本；
- memory backend、embedding、chunk 与 top-k 配置；
- 记忆写入/索引策略；
- answer model、judge models、temperature；
- 每题是否使用隔离 agent session；
- 超时、失败与空回答的处理方式。

## 许可

- 本项目适配代码：MIT License；
- Memora 原始及转换数据：Apache License 2.0；
- 详情见 `data/DATA_LICENSE.md` 与 `data/MEMORA_LICENSE`。
