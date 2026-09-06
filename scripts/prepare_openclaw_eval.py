#!/usr/bin/env python3
"""由 LoCoMo-like JSON 生成 OpenClaw workspace、suite 与评分 sidecar。

评分 rubric 不会写入 suite prompt，避免把正确答案或待遗忘内容泄漏给被测 agent。
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def render_session(date_time: str, messages: list[dict[str, Any]]) -> str:
    """只写入模型真正看到过的对话，不写 evidence/rubric/operation_details。"""
    lines = ["# Memora 对话记忆", "", f"日期：{date_time}", ""]
    for message in messages:
        lines.extend(
            [
                f"## {message['speaker']} [{message['dia_id']}]",
                "",
                message["text"],
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def prepare_sample(sample: dict[str, Any], output_root: Path) -> dict[str, Any]:
    sample_id = safe_name(sample["sample_id"])
    workspace = output_root / "workspaces" / sample_id
    memory_dir = workspace / "memory" / "memora"
    suite_path = output_root / "suites" / f"{sample_id}.jsonl"
    judging_path = output_root / "judging" / f"{sample_id}.jsonl"
    memory_dir.mkdir(parents=True, exist_ok=True)

    conversation = sample["conversation"]
    session_keys = sorted(
        (
            key
            for key in conversation
            if key.startswith("session_") and not key.endswith("_date_time")
        ),
        key=lambda key: int(key.split("_")[1]),
    )
    for key in session_keys:
        number = int(key.split("_")[1])
        content = render_session(
            conversation.get(f"{key}_date_time", ""), conversation[key]
        )
        (memory_dir / f"session_{number:04d}.md").write_text(
            content, encoding="utf-8", newline="\n"
        )

    scenarios: list[dict[str, Any]] = []
    judging_rows: list[dict[str, Any]] = []
    for index, qa in enumerate(sample["qa"]):
        scenario_id = f"{sample_id}-q{index:02d}"
        scenarios.append(
            {
                "id": scenario_id,
                "prompt": qa["question"],
                "tags": [
                    "memora",
                    sample["metadata"]["period"],
                    sample["metadata"]["persona"],
                    qa["question_type"],
                ],
                "source": sample_id,
                "notes": "用 Memora evaluation rubric 与 FAMA 单独评分。",
                "checks": [{"type": "manual"}],
            }
        )
        judging_rows.append(
            {
                "scenario_id": scenario_id,
                "sample_id": sample_id,
                "period": sample["metadata"]["period"],
                "persona": sample["metadata"]["persona"],
                "question_id": qa["question_id"],
                "question_type": qa["question_type"],
                "task_type": qa["task_type"],
                "question": qa["question"],
                "question_date": qa["question_date"],
                "evaluation_questions": qa["evaluation"]["evaluation_questions"],
                "memory_evidence": qa["memory_evidence"],
                "forgetting_evidence": qa["forgetting_evidence"],
            }
        )

    write_jsonl(suite_path, scenarios)
    write_jsonl(judging_path, judging_rows)
    return {
        "sample_id": sample_id,
        "period": sample["metadata"]["period"],
        "persona": sample["metadata"]["persona"],
        "workspace": str(workspace.resolve()),
        "suite": str(suite_path.resolve()),
        "judging": str(judging_path.resolve()),
        "session_count": len(session_keys),
        "question_count": len(scenarios),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="准备 Memora openclaw-eval 输入")
    parser.add_argument("input")
    parser.add_argument("--out", default="generated")
    args = parser.parse_args()

    samples = json.loads(Path(args.input).read_text(encoding="utf-8"))
    output_root = Path(args.out)
    manifest = [prepare_sample(sample, output_root) for sample in samples]
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )

    command_lines = [
        "# 每个 persona 使用独立 workspace，避免跨 persona 记忆污染。",
        "# 先复用你现有 LoCoMo/LongMemEval 的 memory backend 建索引步骤。",
        "",
    ]
    for item in manifest:
        run_dir = str((output_root / "runs" / item["sample_id"]).resolve())
        command_lines.extend(
            [
                (
                    f'openclaw-eval run --setup "{item["sample_id"]}:{item["workspace"]}" '
                    f'--suite "{item["suite"]}" --out "{run_dir}"'
                ),
                "",
            ]
        )
    (output_root / "run_commands.ps1").write_text(
        "\n".join(command_lines), encoding="utf-8", newline="\n"
    )
    print(
        f"已生成 {len(manifest)} 个 workspace、"
        f"{sum(item['question_count'] for item in manifest)} 道题"
    )
    print(f"运行命令：{output_root / 'run_commands.ps1'}")


if __name__ == "__main__":
    main()
