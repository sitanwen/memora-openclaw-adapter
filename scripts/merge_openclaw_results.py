#!/usr/bin/env python3
"""合并 openclaw-eval 运行结果与 Memora 评分 sidecar。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def read_runs(path: Path) -> list[dict[str, Any]]:
    """兼容常见 results.json、JSON 数组与 JSONL 三种输出。"""
    text = path.read_text(encoding="utf-8").strip()
    try:
        bundle = json.loads(text)
    except json.JSONDecodeError:
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    if isinstance(bundle, list):
        return bundle
    if isinstance(bundle, dict):
        for key in ("runs", "results"):
            if isinstance(bundle.get(key), list):
                return bundle[key]
    raise ValueError(f"无法识别 openclaw-eval 结果结构：{path}")


def first_present(row: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in row:
            return row[key]
    return default


def merge_rows(
    runs: list[dict[str, Any]], judging_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    judging_by_id = {row["scenario_id"]: row for row in judging_rows}
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for run in runs:
        scenario_id = first_present(run, "scenarioId", "scenario_id", "id")
        if scenario_id not in judging_by_id:
            raise ValueError(f"sidecar 中不存在 scenario_id：{scenario_id}")
        seen.add(scenario_id)
        merged.append(
            {
                **judging_by_id[scenario_id],
                "setup_id": first_present(run, "setupId", "setup_id"),
                "response": first_present(run, "answer", "response", "output", default=""),
                "status": run.get("status"),
                "error": run.get("error"),
                "latency_seconds": first_present(run, "latencySeconds", "latency_seconds"),
                "prompt_tokens": first_present(run, "promptTokens", "prompt_tokens"),
                "input_tokens": first_present(run, "inputTokens", "input_tokens"),
                "output_tokens": first_present(run, "outputTokens", "output_tokens"),
                "context_tokens": first_present(run, "contextTokens", "context_tokens"),
                "tool_calls": first_present(run, "toolCalls", "tool_calls", default=[]),
                "tool_call_counts": first_present(
                    run, "toolCallCounts", "tool_call_counts", default={}
                ),
                "read_files": first_present(run, "readFiles", "read_files", default=[]),
            }
        )
    missing = sorted(set(judging_by_id) - seen)
    if missing:
        raise ValueError(f"结果缺少 {len(missing)} 个 scenario，例如：{missing[:3]}")
    return merged


def main() -> None:
    parser = argparse.ArgumentParser(description="合并 OpenClaw 答案与 Memora rubric")
    parser.add_argument("results")
    parser.add_argument("judging")
    parser.add_argument("-o", "--output", required=True)
    args = parser.parse_args()

    merged = merge_rows(read_runs(Path(args.results)), read_jsonl(Path(args.judging)))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as file:
        for row in merged:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"已合并 {len(merged)} 条答案 -> {output_path}")


if __name__ == "__main__":
    main()
