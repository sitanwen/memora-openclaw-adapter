#!/usr/bin/env python3
"""按 Memora 官方公式聚合逐题 FAMA，并保留 OpenClaw 成本指标。"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


TASKS = ("remembering", "reasoning", "recommending")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def fama_score(mp_correct: int, mp_total: int, fa_correct: int, fa_total: int) -> float:
    """官方公式：max(0, MPA - lambda * (1 - FAA))。"""
    if mp_total == 0 and fa_total == 0:
        return 0.0
    mpa = mp_correct / mp_total if mp_total else 0.0
    faa = fa_correct / fa_total if fa_total else 1.0
    weight = fa_total / (mp_total + fa_total)
    return max(0.0, mpa - weight * (1.0 - faa))


def score_question(row: dict[str, Any]) -> dict[str, Any]:
    results = row.get("evaluation_results")
    if not results:
        raise ValueError(f"{row.get('scenario_id')} 缺少 evaluation_results；请先运行 judge 脚本")
    mp = [item for item in results if item["evaluation_type"] == "memory_presence"]
    fa = [item for item in results if item["evaluation_type"] == "forgetting_absence"]
    mp_correct = sum(bool(item["is_correct"]) for item in mp)
    fa_correct = sum(bool(item["is_correct"]) for item in fa)
    return {
        "scenario_id": row["scenario_id"],
        "persona": row["persona"],
        "period": row["period"],
        "question_type": row["question_type"],
        "memory_presence_correct": mp_correct,
        "memory_presence_total": len(mp),
        "forgetting_absence_correct": fa_correct,
        "forgetting_absence_total": len(fa),
        "fama": fama_score(mp_correct, len(mp), fa_correct, len(fa)),
        "latency_seconds": row.get("latency_seconds"),
        "input_tokens": row.get("input_tokens"),
        "output_tokens": row.get("output_tokens"),
        "tool_calls": row.get("tool_calls", []),
        "read_files": row.get("read_files", []),
    }


def aggregate_bucket(items: list[dict[str, Any]]) -> dict[str, Any]:
    mp_total = sum(item["memory_presence_total"] for item in items)
    mp_correct = sum(item["memory_presence_correct"] for item in items)
    fa_total = sum(item["forgetting_absence_total"] for item in items)
    fa_correct = sum(item["forgetting_absence_correct"] for item in items)
    return {
        "question_count": len(items),
        # 官方 Table 3：先算每题 FAMA，再对题取均值并乘100。
        "fama": mean(item["fama"] for item in items) * 100 if items else 0.0,
        "memory_presence_accuracy": mp_correct / mp_total if mp_total else None,
        "memory_presence_correct": mp_correct,
        "memory_presence_total": mp_total,
        "forgetting_absence_accuracy": fa_correct / fa_total if fa_total else None,
        "forgetting_absence_correct": fa_correct,
        "forgetting_absence_total": fa_total,
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scored = [score_question(row) for row in rows]
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_persona: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in scored:
        by_task[item["question_type"]].append(item)
        by_persona[item["persona"]].append(item)

    latencies = [item["latency_seconds"] for item in scored if item["latency_seconds"] is not None]
    input_tokens = [item["input_tokens"] for item in scored if item["input_tokens"] is not None]
    output_tokens = [item["output_tokens"] for item in scored if item["output_tokens"] is not None]
    return {
        "overall": aggregate_bucket(scored),
        "by_task_type": {
            task: aggregate_bucket(by_task.get(task, [])) for task in TASKS
        },
        "by_persona": {
            persona: aggregate_bucket(items)
            for persona, items in sorted(by_persona.items())
        },
        "openclaw_runtime": {
            "mean_latency_seconds": mean(latencies) if latencies else None,
            "total_input_tokens": sum(input_tokens) if input_tokens else None,
            "total_output_tokens": sum(output_tokens) if output_tokens else None,
            "total_tool_calls": sum(len(item["tool_calls"]) for item in scored),
            "total_read_files": sum(len(item["read_files"]) for item in scored),
        },
        "detailed_results": scored,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="聚合 Memora FAMA")
    parser.add_argument("input")
    parser.add_argument("-o", "--output", required=True)
    args = parser.parse_args()
    report = aggregate(read_jsonl(Path(args.input)))
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )
    print(f"Overall FAMA: {report['overall']['fama']:.2f} / 100")
    for task, metrics in report["by_task_type"].items():
        print(f"{task}: {metrics['fama']:.2f} / 100 ({metrics['question_count']}题)")
    print(f"报告：{output_path}")


if __name__ == "__main__":
    main()
