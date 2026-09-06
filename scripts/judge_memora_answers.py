#!/usr/bin/env python3
"""使用与 Memora 官方一致的 yes/no rubric 对 OpenClaw 答案评分。

默认采用官方三个 OpenRouter judge 模型并逐 criterion 多数投票。为了低成本冒烟
测试，可传 ``--judge-model openai/gpt-4.1 --limit 1`` 使用单 judge。
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


DEFAULT_JUDGES = [
    "openai/gpt-4.1",
    "anthropic/claude-haiku-4.5",
    "google/gemini-2.5-flash",
]

SYSTEM_PROMPT = """You are an expert evaluator assessing AI assistant responses. Your task is to answer a YES/NO evaluation question about a given response.

You must provide your answer in the following JSON format:
{
    "answer": "yes" or "no",
    "confidence": 0.0 to 1.0,
    "explanation": "Brief explanation of your reasoning"
}

Be objective and thorough in your evaluation."""


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*|\s*```$", "", stripped, flags=re.S)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def call_openrouter(
    api_key: str,
    model: str,
    response: str,
    criterion: dict[str, Any],
    max_retries: int,
) -> dict[str, Any]:
    user_prompt = f"""Please evaluate the following AI response against the evaluation question.

AI RESPONSE TO EVALUATE:
{response}

EVALUATION QUESTION:
{criterion['evaluation_question']}

Evaluation type: {criterion['evaluation_type']}

Provide your evaluation in JSON format with answer (yes/no), confidence (0.0-1.0), and explanation."""
    payload = json.dumps(
        {
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        }
    ).encode("utf-8")

    for attempt in range(max_retries):
        request = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=120) as raw:
                body = json.loads(raw.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"]
            parsed = extract_json(content)
            answer = str(parsed.get("answer", "")).strip().lower()
            if answer not in {"yes", "no"}:
                raise ValueError(f"judge 未返回 yes/no：{content[:200]}")
            expected = criterion["expected_answer"].lower()
            return {
                "judge_model": model,
                "answer": answer,
                "is_correct": answer == expected,
                "confidence": float(parsed.get("confidence", 0.0)),
                "explanation": parsed.get("explanation", ""),
            }
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError) as exc:
            if attempt + 1 == max_retries:
                raise RuntimeError(f"judge {model} 失败：{exc}") from exc
            time.sleep(2**attempt)
    raise AssertionError("unreachable")


def score_criterion(
    api_key: str,
    models: list[str],
    response: str,
    criterion: dict[str, Any],
    max_retries: int,
) -> dict[str, Any]:
    per_judge = [
        call_openrouter(api_key, model, response, criterion, max_retries)
        for model in models
    ]
    yes_votes = sum(item["answer"] == "yes" for item in per_judge)
    no_votes = sum(item["answer"] == "no" for item in per_judge)
    consensus = "yes" if yes_votes > no_votes else "no" if no_votes > yes_votes else "tie"
    expected = criterion["expected_answer"].lower()
    return {
        **criterion,
        "judge_answer": consensus,
        "is_correct": consensus == expected,
        "agreement_rate": max(yes_votes, no_votes) / len(per_judge),
        "per_judge_results": per_judge,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="用官方 Memora rubric 评分答案")
    parser.add_argument("input", help="merge_openclaw_results.py 输出的 JSONL")
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument(
        "--judge-model",
        action="append",
        dest="judge_models",
        help="可重复传入；省略时使用官方三个 judge 模型",
    )
    parser.add_argument("--limit", type=int, help="仅评分前 N 道题，用于冒烟测试")
    parser.add_argument("--max-retries", type=int, default=3)
    args = parser.parse_args()

    api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPEN_ROUTER_API_KEY")
    if not api_key:
        raise SystemExit("请先设置 OPENROUTER_API_KEY（或 OPEN_ROUTER_API_KEY）")
    models = args.judge_models or DEFAULT_JUDGES
    rows = read_jsonl(Path(args.input))
    if args.limit is not None:
        rows = rows[: args.limit]

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="\n") as file:
        for index, row in enumerate(rows, start=1):
            print(f"[{index}/{len(rows)}] {row['scenario_id']}")
            scored = {
                **row,
                "judge_models": models,
                "evaluation_results": [
                    score_criterion(
                        api_key,
                        models,
                        row.get("response", ""),
                        criterion,
                        args.max_retries,
                    )
                    for criterion in row["evaluation_questions"]
                ],
            }
            file.write(json.dumps(scored, ensure_ascii=False) + "\n")
            file.flush()
    print(f"评分完成：{len(rows)} 道题 -> {output_path}")


if __name__ == "__main__":
    main()
