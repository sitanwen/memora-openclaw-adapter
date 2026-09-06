from __future__ import annotations

import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


converter = load_module("converter", ROOT / "scripts" / "convert_memora_to_locomo.py")
validator = load_module("validator", ROOT / "scripts" / "validate_conversion.py")
aggregator = load_module("aggregator", ROOT / "scripts" / "aggregate_fama_scores.py")
merger = load_module("merger", ROOT / "scripts" / "merge_openclaw_results.py")


def test_convert_one_persona_preserves_all_rubrics():
    sample = converter.convert_persona(
        ROOT / "data" / "raw" / "weekly" / "software_engineer", "weekly"
    )
    assert sample["sample_id"] == "memora-weekly-software-engineer"
    assert sample["metadata"]["session_count"] == 163
    assert len(sample["qa"]) == 15
    assert {qa["question_type"] for qa in sample["qa"]} == {
        "remembering",
        "reasoning",
        "recommending",
    }
    assert all(qa["answer"] == "" for qa in sample["qa"])
    assert all(qa["evaluation"]["evaluation_questions"] for qa in sample["qa"])


def test_committed_conversion_is_complete():
    samples = json.loads(
        (ROOT / "data" / "converted" / "memora_weekly_3personas_locomo.json").read_text(
            encoding="utf-8"
        )
    )
    result = validator.validate(samples)
    assert result == {
        "personas": 3,
        "sessions": 466,
        "questions": 45,
        "memory_presence": 148,
        "forgetting_absence": 73,
    }


def test_fama_formula_matches_official_definition():
    assert aggregator.fama_score(2, 2, 2, 2) == 1.0
    assert aggregator.fama_score(2, 2, 0, 2) == 0.5
    assert aggregator.fama_score(1, 2, 0, 2) == 0.0
    assert aggregator.fama_score(3, 4, 0, 0) == 0.75


def test_merge_supports_camel_case_openclaw_fields():
    judging = [{"scenario_id": "s-q00", "evaluation_questions": []}]
    runs = [
        {
            "scenarioId": "s-q00",
            "setupId": "s",
            "answer": "answer text",
            "latencySeconds": 1.5,
            "inputTokens": 10,
            "outputTokens": 3,
        }
    ]
    merged = merger.merge_rows(runs, judging)
    assert merged[0]["response"] == "answer text"
    assert merged[0]["latency_seconds"] == 1.5
    assert merged[0]["input_tokens"] == 10
