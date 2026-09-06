#!/usr/bin/env python3
"""由 LoCoMo-like JSON 生成 OpenClaw workspace、suite 与评分 sidecar。

评分 rubric 不会写入 suite prompt，避免把正确答案或待遗忘内容泄漏给被测 agent。
可用 --sessions-per-file 按时间顺序合并同一 persona 的连续会话，减少逐文件 ingest 次数。
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


def render_session_batch(
    conversation: dict[str, Any], session_keys: list[str]
) -> str:
    """按原始时间顺序合并会话，同时保留每个会话的边界、日期和 dia_id。"""
    sections: list[str] = []
    for key in session_keys:
        number = int(key.split("_")[1])
        session_text = render_session(
            conversation.get(f"{key}_date_time", ""), conversation[key]
        )
        sections.append(
            f"# 原始会话 {number:04d}（{key}）\n\n{session_text.rstrip()}"
        )
    return "\n\n---\n\n".join(sections).rstrip() + "\n"


def prepare_sample(
    sample: dict[str, Any],
    output_root: Path,
    sessions_per_file: int = 1,
) -> dict[str, Any]:
    if sessions_per_file < 1:
        raise ValueError("sessions_per_file 必须大于或等于1")

    sample_id = safe_name(sample["sample_id"])
    workspace = output_root / "workspaces" / sample_id
    memory_dir = workspace / "memory" / "memora"
    suite_path = output_root / "suites" / f"{sample_id}.jsonl"
    judging_path = output_root / "judging" / f"{sample_id}.jsonl"
    memory_dir.mkdir(parents=True, exist_ok=True)

    # 切换批量大小后移除旧的生成文件，避免1-session与批量文件重复进入索引。
    for pattern in ("session_*.md", "sessions_*.md"):
        for old_path in memory_dir.glob(pattern):
            old_path.unlink()

    conversation = sample["conversation"]
    session_keys = sorted(
        (
            key
            for key in conversation
            if key.startswith("session_") and not key.endswith("_date_time")
        ),
        key=lambda key: int(key.split("_")[1]),
    )

    memory_file_count = 0
    for offset in range(0, len(session_keys), sessions_per_file):
        batch_keys = session_keys[offset : offset + sessions_per_file]
        first_number = int(batch_keys[0].split("_")[1])
        last_number = int(batch_keys[-1].split("_")[1])

        if len(batch_keys) == 1:
            filename = f"session_{first_number:04d}.md"
            key = batch_keys[0]
            content = render_session(
                conversation.get(f"{key}_date_time", ""), conversation[key]
            )
        else:
            filename = f"sessions_{first_number:04d}-{last_number:04d}.md"
            content = render_session_batch(conversation, batch_keys)

        (memory_dir / filename).write_text(
            content, encoding="utf-8", newline="\n"
        )
        memory_file_count += 1

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
        "memory_file_count": memory_file_count,
        "sessions_per_file": sessions_per_file,
        "question_count": len(scenarios),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="准备 Memora openclaw-eval 输入")
    parser.add_argument("input")
    parser.add_argument("--out", default="generated")
    parser.add_argument(
        "--sessions-per-file",
        type=int,
        default=1,
        help=(
            "同一 persona 中每个记忆文件合并的连续 session 数；"
            "默认1保持原始行为，建议低成本运行使用10"
        ),
    )
    args = parser.parse_args()
    if args.sessions_per_file < 1:
        parser.error("--sessions-per-file 必须大于或等于1")

    samples = json.loads(Path(args.input).read_text(encoding="utf-8"))
    output_root = Path(args.out)
    manifest = [
        prepare_sample(sample, output_root, args.sessions_per_file)
        for sample in samples
    ]
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )

    command_lines = [
        "# 每个 persona 使用独立 workspace，避免跨 persona 记忆污染。",
        "# 先复用你现有 LoCoMo/LongMemEval 的 memory backend 建索引步骤。",
        f"# sessions_per_file={args.sessions_per_file}",
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

    total_sessions = sum(item["session_count"] for item in manifest)
    total_memory_files = sum(item["memory_file_count"] for item in manifest)
    print(
        f"已生成 {len(manifest)} 个 workspace、"
        f"{sum(item['question_count'] for item in manifest)} 道题；"
        f"{total_sessions} sessions -> {total_memory_files} 个记忆文件"
    )
    print(f"运行命令：{output_root / 'run_commands.ps1'}")


if __name__ == "__main__":
    main()
