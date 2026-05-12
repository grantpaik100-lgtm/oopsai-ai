from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
SCENARIO_PATH = BASE_DIR / "data" / "severity_scenarios.json"

sys.path.insert(0, str(BASE_DIR))
from services.severity_engine import predict_severity  # noqa: E402

REQUIRED_TOP_LEVEL_FIELDS = {
    "id",
    "name",
    "severity_group",
    "situation_text",
    "normalized",
    "expected",
    "notes",
}

REQUIRED_NORMALIZED_FIELDS = {
    "accident_type",
    "work_type",
    "hazard_major_category",
    "hazard_middle_category",
    "secondary_hazards",
    "environment_factors",
    "human_factors",
    "equipment",
}

REQUIRED_EXPECTED_FIELDS = {
    "grade",
    "confidence",
    "must_include_reason_keywords",
    "why_not_higher_keywords",
    "why_not_lower_keywords",
    "missing_information_keywords",
    "validation_warning_keywords",
}

VALID_GRADES = {"A", "B", "C", "D", "E", None}
VALID_CONFIDENCE = {"high", "medium", "low"}
EXPECTED_DISTRIBUTION = {
    "A": 2,
    "B": 3,
    "C": 6,
    "D": 5,
    "E": 2,
    "UNKNOWN": 2,
}


def load_scenarios() -> list[dict[str, Any]]:
    if not SCENARIO_PATH.exists():
        raise FileNotFoundError(f"Scenario file not found: {SCENARIO_PATH}")
    with SCENARIO_PATH.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("severity_scenarios.json must be a list")
    return data


def require_fields(
    obj: dict[str, Any],
    required: set[str],
    scenario_id: str,
    scope: str,
) -> list[str]:
    failures: list[str] = []
    for field in sorted(required - set(obj.keys())):
        failures.append(f"{scenario_id}: missing {scope}.{field}")
    return failures


def validate_list_field(value: Any, scenario_id: str, field_name: str) -> list[str]:
    if not isinstance(value, list):
        return [f"{scenario_id}: expected.{field_name} must be list"]
    if not all(isinstance(item, str) for item in value):
        return [f"{scenario_id}: expected.{field_name} must contain only strings"]
    return []


def validate_secondary_hazards(value: Any, scenario_id: str) -> list[str]:
    failures: list[str] = []
    if not isinstance(value, list):
        return [f"{scenario_id}: normalized.secondary_hazards must be list"]
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            failures.append(f"{scenario_id}: secondary_hazards[{idx}] must be object")
            continue
        for field in ("major", "middle", "evidence"):
            if field not in item:
                failures.append(f"{scenario_id}: secondary_hazards[{idx}] missing {field}")
            elif not isinstance(item[field], str):
                failures.append(f"{scenario_id}: secondary_hazards[{idx}].{field} must be string")
    return failures


def validate_schema(scenario: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    scenario_id = str(scenario.get("id", "(unknown)"))
    failures.extend(require_fields(scenario, REQUIRED_TOP_LEVEL_FIELDS, scenario_id, "scenario"))

    normalized = scenario.get("normalized")
    expected = scenario.get("expected")

    if not isinstance(normalized, dict):
        failures.append(f"{scenario_id}: normalized must be object")
        normalized = {}
    if not isinstance(expected, dict):
        failures.append(f"{scenario_id}: expected must be object")
        expected = {}

    failures.extend(require_fields(normalized, REQUIRED_NORMALIZED_FIELDS, scenario_id, "normalized"))
    failures.extend(require_fields(expected, REQUIRED_EXPECTED_FIELDS, scenario_id, "expected"))

    severity_group = scenario.get("severity_group")
    grade = expected.get("grade")
    confidence = expected.get("confidence")

    if severity_group not in {"A", "B", "C", "D", "E", "UNKNOWN"}:
        failures.append(f"{scenario_id}: severity_group must be A/B/C/D/E/UNKNOWN")
    if grade not in VALID_GRADES:
        failures.append(f"{scenario_id}: expected.grade must be A/B/C/D/E/null")
    if confidence not in VALID_CONFIDENCE:
        failures.append(f"{scenario_id}: expected.confidence must be high/medium/low")

    if severity_group == "UNKNOWN":
        if grade is not None:
            failures.append(f"{scenario_id}: UNKNOWN scenario must have grade=null")
        if confidence != "low":
            failures.append(f"{scenario_id}: UNKNOWN scenario must have confidence=low")
        missing_info = expected.get("missing_information_keywords", [])
        if not isinstance(missing_info, list) or len(missing_info) == 0:
            failures.append(f"{scenario_id}: UNKNOWN scenario must include missing_information_keywords")
    else:
        if grade != severity_group:
            failures.append(f"{scenario_id}: expected.grade must match severity_group ({severity_group})")
        reason_kw = expected.get("must_include_reason_keywords", [])
        if not isinstance(reason_kw, list) or len(reason_kw) == 0:
            failures.append(f"{scenario_id}: non-UNKNOWN scenario should include reason keywords")

    for field in (
        "must_include_reason_keywords",
        "why_not_higher_keywords",
        "why_not_lower_keywords",
        "missing_information_keywords",
        "validation_warning_keywords",
    ):
        failures.extend(validate_list_field(expected.get(field), scenario_id, field))

    failures.extend(validate_secondary_hazards(normalized.get("secondary_hazards"), scenario_id))
    for field in ("environment_factors", "human_factors"):
        if not isinstance(normalized.get(field), list):
            failures.append(f"{scenario_id}: normalized.{field} must be list")
    if not isinstance(scenario.get("situation_text"), str) or not scenario.get("situation_text", "").strip():
        failures.append(f"{scenario_id}: situation_text must be non-empty string")
    if not isinstance(scenario.get("notes"), str) or not scenario.get("notes", "").strip():
        failures.append(f"{scenario_id}: notes must be non-empty string")
    return failures


def _keywords_found(keywords: list[str], text: str) -> bool:
    if not keywords:
        return True
    return any(kw in text for kw in keywords)


def _keywords_in_list(keywords: list[str], items: list[str]) -> bool:
    if not keywords:
        return True
    joined = " ".join(items)
    return any(kw in joined for kw in keywords)


def evaluate_prediction(scenario: dict[str, Any]) -> tuple[bool, list[str]]:
    scenario_id = str(scenario.get("id", ""))
    expected = scenario.get("expected", {})
    normalized = scenario.get("normalized", {})
    situation_text = scenario.get("situation_text", "")

    result = predict_severity(normalized=normalized, situation_text=situation_text)

    expected_grade = expected.get("grade")
    actual_grade = result.grade

    failures: list[str] = []

    # grade 일치 확인
    if actual_grade != expected_grade:
        failures.append(f"grade: expected={expected_grade} actual={actual_grade}")

    # UNKNOWN이면 confidence=low 확인
    if expected_grade is None and result.confidence != "low":
        failures.append(f"confidence: expected=low actual={result.confidence}")

    # must_include_reason_keywords
    reason_text = " ".join(result.prediction_reason)
    reason_kws = expected.get("must_include_reason_keywords", [])
    if reason_kws and not _keywords_found(reason_kws, reason_text):
        failures.append(f"prediction_reason missing keywords: {reason_kws}")

    # why_not_higher_keywords
    wnh_kws = expected.get("why_not_higher_keywords", [])
    if wnh_kws and not _keywords_found(wnh_kws, result.why_not_higher):
        failures.append(f"why_not_higher missing keywords: {wnh_kws}")

    # why_not_lower_keywords
    wnl_kws = expected.get("why_not_lower_keywords", [])
    if wnl_kws and not _keywords_found(wnl_kws, result.why_not_lower):
        failures.append(f"why_not_lower missing keywords: {wnl_kws}")

    # missing_information_keywords
    mi_kws = expected.get("missing_information_keywords", [])
    if mi_kws and not _keywords_in_list(mi_kws, result.missing_information):
        failures.append(f"missing_information missing keywords: {mi_kws}")

    # validation_warning_keywords
    vw_kws = expected.get("validation_warning_keywords", [])
    if vw_kws and not _keywords_in_list(vw_kws, result.validation_warnings):
        failures.append(f"validation_warnings missing keywords: {vw_kws}")

    return len(failures) == 0, failures


def main() -> int:
    scenarios = load_scenarios()

    # ── 스키마 검증 ────────────────────────────────────────────────
    schema_failures: list[str] = []
    ids = [str(item.get("id")) for item in scenarios]
    for dup in [item for item, count in Counter(ids).items() if count > 1]:
        schema_failures.append(f"duplicate scenario id: {dup}")
    distribution = Counter(str(item.get("severity_group")) for item in scenarios)
    for scenario in scenarios:
        if isinstance(scenario, dict):
            schema_failures.extend(validate_schema(scenario))
        else:
            schema_failures.append("scenario item must be object")

    print("Severity scenario validation")
    print(f"Total: {len(scenarios)}")
    for grade in ("A", "B", "C", "D", "E", "UNKNOWN"):
        print(f"{grade}: {distribution.get(grade, 0)}")

    print("")
    print("Expected distribution")
    dist_ok = True
    for grade, expected_count in EXPECTED_DISTRIBUTION.items():
        actual_count = distribution.get(grade, 0)
        status = "PASS" if actual_count == expected_count else "FAIL"
        print(f"- {grade}: expected={expected_count} actual={actual_count} {status}")
        if actual_count != expected_count:
            dist_ok = False
            schema_failures.append(
                f"distribution mismatch for {grade}: expected={expected_count} actual={actual_count}"
            )

    if schema_failures:
        print("")
        print(f"Schema failures: {len(schema_failures)}")
        for f in schema_failures:
            print(f"  - {f}")
        return 1

    # ── predict_severity 검증 ──────────────────────────────────────
    print("")
    print("Severity prediction evaluation")
    print("")

    passed = 0
    failed = 0
    fail_details: list[str] = []

    for scenario in scenarios:
        scenario_id = str(scenario.get("id", ""))
        name = str(scenario.get("name", ""))
        expected_grade = scenario.get("expected", {}).get("grade")
        result = predict_severity(
            normalized=scenario.get("normalized", {}),
            situation_text=scenario.get("situation_text", ""),
        )
        ok, failures = evaluate_prediction(scenario)

        status = "PASS" if ok else "FAIL"
        grade_str = result.grade if result.grade is not None else "null"
        exp_str = expected_grade if expected_grade is not None else "null"
        print(f"[{status}] {scenario_id} {name}")
        print(f"  expected grade {exp_str} / actual {grade_str} / confidence={result.confidence}")

        if ok:
            passed += 1
        else:
            failed += 1
            for f in failures:
                print(f"  FAIL: {f}")
            fail_details.append(f"{scenario_id} {name}")

        print()

    total = passed + failed
    accuracy = (passed / total * 100) if total else 0
    print("Summary")
    print(f"Total: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Accuracy: {accuracy:.1f}%")
    if fail_details:
        print("Failed IDs: " + ", ".join(fail_details))

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
