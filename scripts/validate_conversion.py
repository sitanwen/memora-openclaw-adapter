#!/usr/bin/env python3
"""校验固定 Memora 转换结果的数量、结构和 FAMA rubric。"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


EXPECTED_PERSONAS = {
    "software_engineer": 163,
    "financial_analyst": 156,
    "creative_designer": 147,
}
EXPECTED_TASK_COUNTS = {
    "remembering": 15,
    "reasoning": 15,
    "recommending": 15,
}


def validate(samples: list[dict]) -> dict[str, int]:
    assert len(samples) == 3, f"应有3个 persona，实际为 {len(samples)}"
    task_counts: Counter[str] = Counter()
    eval_counts: Counter[str] = Counter()
    session_total = 0

    seen_personas = set()
    for sample in samples:
        metadata = sample["metadata"]
        assert metadata["dataset"] == "Memora"
        assert metadata["period"] == "weekly"
        persona = metadata["persona"]
        seen_personas.add(persona)
        expected_sessions = EXPECTED_PERSONAS[persona]
        assert metadata["session_count"] == expected_sessions
        assert len(sample["session_metadata"]) == expected_sessions
        assert len(sample["qa"]) == 15
        conversation_sessions = [
            key
            for key in sample["conversation"]
            if key.startswith("session_") and not key.endswith("_date_time")
        ]
        assert len(conversation_sessions) == expected_sessions
        session_total += expected_sessions

        for qa in sample["qa"]:
            assert qa["question"].strip()
            assert qa["answer"] == "", "Memora 不应伪造自由文本 gold answer"
            task_counts[qa["question_type"]] += 1
            evaluation = qa["evaluation"]
            rows = evaluation["evaluation_questions"]
            assert rows, f"{qa['question_id']} 缺少 evaluation rubric"
            assert len(rows) == evaluation["total_evaluation_questions"]
            for row in rows:
                eval_type = row["evaluation_type"]
                assert eval_type in {"memory_presence", "forgetting_absence"}
                assert row["expected_answer"] in {"yes", "no"}
                eval_counts[eval_type] += 1

    assert seen_personas == set(EXPECTED_PERSONAS)
    assert dict(task_counts) == EXPECTED_TASK_COUNTS
    assert eval_counts["memory_presence"] == 148
    assert eval_counts["forgetting_absence"] == 73
    return {
        "personas": len(samples),
        "sessions": session_total,
        "questions": sum(task_counts.values()),
        "memory_presence": eval_counts["memory_presence"],
        "forgetting_absence": eval_counts["forgetting_absence"],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="校验 Memora 转换结果")
    parser.add_argument("input")
    args = parser.parse_args()
    samples = json.loads(Path(args.input).read_text(encoding="utf-8"))
    result = validate(samples)
    print(
        "校验通过：{personas} personas，{sessions} sessions，{questions} QA；"
        "memory_presence={memory_presence}，forgetting_absence={forgetting_absence}".format(
            **result
        )
    )


if __name__ == "__main__":
    main()
