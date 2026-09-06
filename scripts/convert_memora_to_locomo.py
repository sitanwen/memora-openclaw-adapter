#!/usr/bin/env python3
"""把 Memora persona-period 目录转换成 LoCoMo-like JSON。

转换原则：
- 一个 persona-period 对应一个 sample，所有问题共用同一份记忆；
- 会话严格按 session_id 排序；
- 保留 Memora 的 memory/forgetting evidence 与逐项 evaluation rubric；
- ``answer`` 留空，因为 Memora 官方没有单一自由文本参考答案，不能用 EM/F1 评分。
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable


TASK_TO_CATEGORY = {
    "remembering": 1,
    "reasoning": 2,
    "recommending": 3,
}

SPEAKER_MAP = {
    "user": "User",
    "user_agent": "User",
    "assistant": "Assistant",
    "ai_agent": "Assistant",
}


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as file:
        return json.load(file)


def session_number(path: Path) -> int:
    """从 session_NNNN.json 中读取排序号。"""
    match = re.fullmatch(r"session_(\d+)\.json", path.name)
    if not match:
        raise ValueError(f"非法会话文件名：{path}")
    return int(match.group(1))


def walk_session_ids(value: Any) -> Iterable[int]:
    """递归提取 evidence 结构里的 session_id。"""
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "session_id" and isinstance(child, int):
                yield child
            else:
                yield from walk_session_ids(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_session_ids(child)


def convert_session(
    ordinal: int,
    raw_session: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[str]]:
    """转换单个 Memora 会话，并返回对话及该会话全部 dia_id。"""
    messages: list[dict[str, Any]] = []
    dia_ids: list[str] = []
    for fallback_turn, message in enumerate(raw_session["conversation"], start=1):
        turn = int(message.get("turn", fallback_turn))
        dia_id = f"D{ordinal}:{turn}"
        speaker_raw = str(message.get("speaker", ""))
        if speaker_raw not in SPEAKER_MAP:
            raise ValueError(f"未知 speaker：{speaker_raw}")
        messages.append(
            {
                "speaker": SPEAKER_MAP[speaker_raw],
                "dia_id": dia_id,
                "text": str(message.get("message", "")),
                "share_memory": bool(message.get("share_memory", False)),
            }
        )
        dia_ids.append(dia_id)
    return messages, dia_ids


def convert_persona(persona_dir: Path, period: str) -> dict[str, Any]:
    """转换一个 persona 的全部会话与问题。"""
    persona = persona_dir.name
    question_path = persona_dir / f"evaluation_questions_{persona}.json"
    question_bundle = load_json(question_path)
    if question_bundle.get("persona") != persona:
        raise ValueError(f"persona 不一致：{question_path}")

    session_paths = sorted(
        (persona_dir / "conversations").glob("session_*.json"),
        key=session_number,
    )
    if not session_paths:
        raise ValueError(f"没有找到会话：{persona_dir}")

    conversation: dict[str, Any] = {
        "speaker_a": "User",
        "speaker_b": "Assistant",
    }
    session_metadata: list[dict[str, Any]] = []
    original_to_dia_ids: dict[int, list[str]] = {}

    for ordinal, path in enumerate(session_paths, start=1):
        raw_session = load_json(path)
        original_id = int(raw_session["session_id"])
        if original_id != session_number(path):
            raise ValueError(f"文件名与 session_id 不一致：{path}")
        messages, dia_ids = convert_session(ordinal, raw_session)
        conversation[f"session_{ordinal}"] = messages
        conversation[f"session_{ordinal}_date_time"] = raw_session.get("date", "")
        original_to_dia_ids[original_id] = dia_ids
        session_metadata.append(
            {
                "session_index": ordinal,
                "original_session_id": original_id,
                "date": raw_session.get("date", ""),
                "session_type": raw_session.get("session_type", ""),
                "operation": raw_session.get("operation", ""),
            }
        )

    qa: list[dict[str, Any]] = []
    for task_name in ("remembering", "reasoning", "recommending"):
        questions = question_bundle["questions"].get(task_name, [])
        for question in questions:
            memory_evidence = question.get("memory_evidence", {})
            forgetting_evidence = question.get("forgetting_evidence", {})
            evidence_session_ids = sorted(
                set(walk_session_ids(memory_evidence))
                | set(walk_session_ids(forgetting_evidence))
            )
            unknown_ids = [
                session_id
                for session_id in evidence_session_ids
                if session_id not in original_to_dia_ids
            ]
            if unknown_ids:
                raise ValueError(
                    f"{question['question_id']} 引用了不存在的 session：{unknown_ids}"
                )
            evidence = [
                dia_id
                for original_id in evidence_session_ids
                for dia_id in original_to_dia_ids.get(original_id, [])
            ]
            evaluation = question.get("evaluation", {})
            qa.append(
                {
                    "question_id": question["question_id"],
                    "question": question["question"],
                    "question_date": question.get("question_date", ""),
                    "answer": "",
                    "evidence": evidence,
                    "category": TASK_TO_CATEGORY[task_name],
                    "question_type": task_name,
                    "task_type": task_name.title(),
                    "memory_evidence": memory_evidence,
                    "forgetting_evidence": forgetting_evidence,
                    "evaluation": evaluation,
                }
            )

    return {
        "sample_id": f"memora-{period}-{persona.replace('_', '-')}",
        "metadata": {
            "dataset": "Memora",
            "period": period,
            "persona": persona,
            "date_range": question_bundle.get("date_range", {}),
            "session_count": len(session_paths),
            "question_count": len(qa),
            "scoring": "FAMA",
        },
        "conversation": conversation,
        "session_metadata": session_metadata,
        "qa": qa,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="把 Memora 转换为 LoCoMo-like JSON")
    parser.add_argument("input", help="例如 data/raw/weekly")
    parser.add_argument("-o", "--output", required=True, help="输出 JSON")
    parser.add_argument("--period", default="weekly")
    parser.add_argument(
        "--personas",
        nargs="*",
        help="指定 persona；省略时转换输入目录下的全部 persona",
    )
    args = parser.parse_args()

    input_root = Path(args.input)
    persona_names = args.personas or sorted(
        path.name for path in input_root.iterdir() if path.is_dir()
    )
    samples = [
        convert_persona(input_root / persona, args.period) for persona in persona_names
    ]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(samples, ensure_ascii=False, indent=2),
        encoding="utf-8",
        newline="\n",
    )

    total_sessions = sum(item["metadata"]["session_count"] for item in samples)
    total_questions = sum(len(item["qa"]) for item in samples)
    print(
        f"转换完成：{len(samples)} personas，{total_sessions} sessions，"
        f"{total_questions} QA -> {output_path}"
    )


if __name__ == "__main__":
    main()
