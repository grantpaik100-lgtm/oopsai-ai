from __future__ import annotations

from typing import Any

from models.schemas import PredictedSeverity

_GRADE_LABELS: dict[str | None, str] = {
    "A": "예상 피해등급 A",
    "B": "예상 피해등급 B",
    "C": "예상 피해등급 C",
    "D": "예상 피해등급 D",
    "E": "예상 피해등급 E",
    None: "예상 피해등급 판단 보류",
}

_WHY_NOT_HIGHER_A = ""
_WHY_NOT_HIGHER_B = "3명 이상 사망, 7명 이상 중상, 20억원 이상 물적피해 가능성이 명시되지 않았습니다."
_WHY_NOT_HIGHER_C = "다수 사망, 다수 중상, 대규모 물적피해 가능성이 명시되지 않았습니다."
_WHY_NOT_HIGHER_D = "중상 가능성, 5일 이상 근무 불가 가능성이 명시되지 않았습니다."
_WHY_NOT_HIGHER_E = "중상, 사망, 대규모 물적피해 가능성이 명시되지 않았습니다."

_WHY_NOT_LOWER_A = "폭발물/대형차량과 다수 인원 노출 조합으로 3명 이상 사망 또는 7명 이상 중상 가능성이 있습니다."
_WHY_NOT_LOWER_B = "5명 이상 중상 가능성, 질식·밀폐공간 노출 위험, 폭발물·다수 작업자 위험이 확인되어 단순 개인 부상으로 보기 어렵습니다."
_WHY_NOT_LOWER_C = "중상 가능성이 있어 단순 경상으로 보기 어렵습니다."
_WHY_NOT_LOWER_E = ""


def predict_severity(
    normalized: dict[str, Any],
    situation_text: str | None = None,
) -> PredictedSeverity:
    src = (situation_text or "").lower()
    accident_type = str(normalized.get("accident_type") or "")
    hazard_middle = str(normalized.get("hazard_middle_category") or "")
    hazard_major = str(normalized.get("hazard_major_category") or "")
    equipment = str(normalized.get("equipment") or "")
    secondary = normalized.get("secondary_hazards") or []
    secondary_middles = [
        str(s.get("middle", "") if isinstance(s, dict) else getattr(s, "middle", ""))
        for s in secondary
    ]

    # ── 정보부족 ──────────────────────────────────────────────────
    if _is_vague(src, accident_type, hazard_middle):
        return _unknown_result()

    # ── E 우선 판단 (경미 단서가 명확하면 즉시 반환) ─────────────
    if _is_grade_e(src):
        return _make_e(src, accident_type)

    # ── A 판단 ─────────────────────────────────────────────────────
    if _is_grade_a(src, accident_type):
        return _make_a(src, accident_type)

    # ── B 판단 ─────────────────────────────────────────────────────
    if _is_grade_b(src, accident_type):
        return _make_b(src, accident_type)

    # ── C 판단 ─────────────────────────────────────────────────────
    if _is_grade_c(src, accident_type, hazard_middle, equipment):
        return _make_c(src, accident_type, hazard_middle, equipment)

    # ── D 기본 ─────────────────────────────────────────────────────
    return _make_d(src, accident_type, hazard_middle)


# ── 판단 헬퍼 ─────────────────────────────────────────────────────────

def _is_vague(src: str, accident_type: str, hazard_middle: str) -> bool:
    if accident_type in ("기타", "") and hazard_middle in ("기타", ""):
        return True
    vague_phrases = ["위험했습니다", "사고 날 뻔했습니다", "다칠 뻔했습니다"]
    if any(p in src for p in vague_phrases) and len(src) < 30:
        return True
    return False


def _is_grade_a(src: str, accident_type: str) -> bool:
    # 폭발물/신관/탄약고 + 다수 인원: 텍스트 직접 단서 필수
    has_explosive_text = any(kw in src for kw in ["폭발물", "신관", "탄약고"])
    has_large_vehicle = any(kw in src for kw in ["장갑차", "전차", "대형 군용차량"])
    has_multiple = any(kw in src for kw in ["다수", "여러 명", "7명 이상", "주변 병력"])

    if has_explosive_text and has_multiple:
        return True
    if has_large_vehicle and has_multiple and accident_type == "교통":
        return True
    return False


def _is_grade_b(src: str, accident_type: str) -> bool:
    # 5~6명 이상 충돌·중상 가능성
    has_five_plus = any(kw in src for kw in ["5~6명", "5∼6명", "5명", "6명"])
    if has_five_plus and any(kw in src for kw in ["충돌", "중상", "부상", "병사", "작업자"]):
        return True
    # 밀폐공간 질식 + 5명 이상
    if accident_type == "질식·익사" and any(kw in src for kw in ["5명", "5~6명", "여러 명", "다수"]):
        return True
    # 폭발물 + 운반장비 충돌 + 주변 작업자 (A 기준 미달)
    if accident_type == "폭발·파열" and any(kw in src for kw in ["지게차", "운반", "충돌"]) and any(
        kw in src for kw in ["주변", "작업자", "여러 명"]
    ):
        return True
    return False


def _is_grade_c(src: str, accident_type: str, hazard_middle: str, equipment: str) -> bool:
    if any(kw in src for kw in ["눈", "안구"]) and accident_type == "충격":
        return True
    if accident_type == "추락":
        return True
    if accident_type == "감전":
        return True
    # 절단기/전동공구 사용 중 손가락 절단 — 절단기 장비 단서 필수
    if accident_type == "절단·베임" and any(kw in src for kw in ["절단기", "전동공구", "그라인더"]):
        return True
    # 지게차/차량 단일 인원 충돌
    if accident_type == "교통" and any(kw in src for kw in ["지게차", "충돌"]) and not any(
        kw in src for kw in ["다수", "여러 명", "5명", "6명", "장갑차"]
    ):
        return True
    if hazard_middle == "낙하물" and any(kw in src for kw in ["머리", "두부"]):
        return True
    if accident_type == "끼임" and any(kw in src for kw in ["절단", "중상", "손가락이 잘"]):
        return True
    return False


def _is_grade_e(src: str) -> bool:
    e_phrases = ["살짝 휘청", "넘어지지는 않", "넘어지지 않", "살짝 베일", "경미", "살짝 닿"]
    return any(p in src for p in e_phrases)


# ── 각 등급 결과 생성 ─────────────────────────────────────────────────

def _make_a(src: str, accident_type: str) -> PredictedSeverity:
    reasons: list[str] = []
    if any(kw in src for kw in ["폭발물", "신관", "탄약고"]):
        reasons.append("폭발물/신관 충격 위험이 탄약고 내에서 확인되었습니다.")
    if any(kw in src for kw in ["장갑차", "전차"]):
        reasons.append("대형 군용차량(장갑차/전차) 기동 중 다수 인원 압착·충돌 위험이 있습니다.")
    if any(kw in src for kw in ["다수", "여러 명", "주변 병력"]):
        reasons.append("다수 인원이 위험 구역에 노출되어 있었습니다.")

    missing: list[str] = ["정확한 노출 인원", "폭발물 종류"]
    if any(kw in src for kw in ["장갑차", "전차", "차량"]):
        missing = ["노출 인원 수", "차량 속도"]

    warnings = [
        "A등급은 폭발 가능성과 다수 인원 노출 근거가 있을 때만 허용",
        "다수 인원 노출 근거 없이 A등급을 남발하지 말 것",
    ]
    return PredictedSeverity(
        grade="A",
        label=_GRADE_LABELS["A"],
        is_actual_damage=False,
        confidence="medium",
        prediction_reason=reasons or ["폭발물 또는 대형차량과 다수 인원 노출 조합이 확인되었습니다."],
        why_not_higher=_WHY_NOT_HIGHER_A,
        why_not_lower=_WHY_NOT_LOWER_A,
        missing_information=missing,
        validation_warnings=warnings,
    )


def _make_b(src: str, accident_type: str) -> PredictedSeverity:
    reasons: list[str] = []
    if any(kw in src for kw in ["5~6명", "5명", "6명", "5∼6명"]):
        reasons.append("5~6명의 병사/작업자가 위험에 노출될 가능성이 있습니다.")
    if accident_type == "질식·익사":
        reasons.append("밀폐공간 질식 위험으로 다수 인원이 동시에 영향을 받을 수 있습니다.")
    if accident_type == "폭발·파열":
        reasons.append("폭발물과 지게차 충돌 가능성이 있어 주변 작업자에 대한 위험이 있습니다.")
    if any(kw in src for kw in ["주변 작업자", "주변에 작업자"]):
        reasons.append("충돌 또는 폭발 반경 내 주변 작업자가 있었습니다.")

    missing: list[str] = []
    if accident_type == "교통":
        missing.extend(["차량 속도", "정확한 노출 인원"])
    if accident_type == "질식·익사":
        missing.extend(["산소 농도", "작업 시간"])
    if accident_type == "폭발·파열":
        missing.extend(["탄약 종류", "주변 인원 수"])

    return PredictedSeverity(
        grade="B",
        label=_GRADE_LABELS["B"],
        is_actual_damage=False,
        confidence="medium",
        prediction_reason=reasons or ["5명 이상 중상 가능성이 있는 상황이 확인되었습니다."],
        why_not_higher=_WHY_NOT_HIGHER_B,
        why_not_lower=_WHY_NOT_LOWER_B,
        missing_information=missing,
        validation_warnings=[],
    )


def _make_c(src: str, accident_type: str, hazard_middle: str, equipment: str) -> PredictedSeverity:
    reasons: list[str] = []
    if accident_type == "감전":
        reasons.append("감전 사고는 전원 미차단 상태에서 정비 중 중상 가능성이 있습니다.")
    if accident_type == "추락":
        reasons.append("고소작업 추락은 중상 이상 가능성이 있습니다.")
    if any(kw in src for kw in ["눈", "안구"]):
        reasons.append("안구 손상은 중상 이상으로 이어질 수 있습니다.")
    if accident_type == "절단·베임":
        reasons.append("절단기 작업 중 손가락 절단 가능성은 중상에 해당합니다.")
    if accident_type == "교통" and any(kw in src for kw in ["지게차", "충돌"]):
        reasons.append("지게차와 보행자 충돌로 단일 인원 중상 가능성이 있습니다.")
    if hazard_middle == "낙하물":
        reasons.append("낙하물이 머리 부위에 충격을 줄 경우 중상 가능성이 있습니다.")

    missing: list[str] = []
    if hazard_middle == "낙하물":
        missing.extend(["낙하 높이", "물자 무게", "안전모 착용 여부"])
    elif accident_type == "감전":
        missing.extend(["전압", "차단 여부"])
    elif accident_type == "추락":
        missing.extend(["작업 높이", "추락 방지 설비"])
    elif accident_type == "절단·베임":
        missing.extend(["절단 깊이", "보호구 상태"])
    elif accident_type == "교통":
        missing.extend(["지게차 속도", "보행자 위치"])
    elif accident_type == "충격":
        missing.extend(["비산 강도", "보호구 상태"])

    return PredictedSeverity(
        grade="C",
        label=_GRADE_LABELS["C"],
        is_actual_damage=False,
        confidence="medium",
        prediction_reason=reasons or [f"{accident_type} 사고는 단일 인원 중상 가능성이 있습니다."],
        why_not_higher=_WHY_NOT_HIGHER_C,
        why_not_lower=_WHY_NOT_LOWER_C,
        missing_information=missing,
        validation_warnings=[],
    )


def _make_d(src: str, accident_type: str, hazard_middle: str) -> PredictedSeverity:
    reasons: list[str] = []
    if accident_type == "낙상":
        reasons.append("미끄러짐 또는 넘어짐으로 경상 또는 단기 근무 제한 가능성이 있습니다.")
    if accident_type == "화재·화상":
        reasons.append("손 부위 화상 가능성으로 치료 후 단기 근무 제한이 필요할 수 있습니다.")
    if accident_type == "과부하·온열":
        reasons.append("중량물 운반 또는 온열 노출로 허리 부상 및 단기 근무 제한 가능성이 있습니다.")
    if accident_type == "끼임":
        reasons.append("손가락 끼임 가능성이 있으나 절단/중상 직접 단서가 부족합니다.")
    if hazard_middle == "야간/조도불량":
        reasons.append("조도 부족으로 인한 넘어짐 위험이 확인되었습니다.")

    # 사고유형별 why_not_lower
    if accident_type == "화재·화상":
        why_not_lower = "화상 가능성이 있어 경미상만으로 보기 어려우며 치료 가능성이 있습니다."
    elif accident_type == "끼임":
        why_not_lower = "손가락 끼임 치료 가능성이 있어 경미상으로만 보기 어렵습니다."
    elif accident_type == "과부하·온열":
        why_not_lower = "허리 부상 및 근무 제한 가능성이 있어 경미상으로만 보기 어렵습니다."
    else:
        why_not_lower = "경상 또는 단기 근무 제한 가능성이 있어 경미상으로만 보기 어렵습니다."

    missing: list[str] = []
    if accident_type == "낙상":
        missing.extend(["충격 부위"])
    elif accident_type == "화재·화상":
        missing.extend(["화상 범위", "보호장갑 착용 여부"])
    elif accident_type == "과부하·온열":
        missing.extend(["중량", "운반 거리"])
    elif accident_type == "끼임":
        missing.extend(["회전부 속도", "손상 정도"])

    return PredictedSeverity(
        grade="D",
        label=_GRADE_LABELS["D"],
        is_actual_damage=False,
        confidence="medium",
        prediction_reason=reasons or [f"{accident_type} 사고유형으로 경상 또는 단기 근무 제한 가능성이 있습니다."],
        why_not_higher=_WHY_NOT_HIGHER_D,
        why_not_lower=why_not_lower,
        missing_information=missing,
        validation_warnings=[],
    )


def _make_e(src: str, accident_type: str) -> PredictedSeverity:
    reasons: list[str] = []
    if "살짝 휘청" in src or "넘어지지" in src:
        reasons.append("실제 넘어짐이 없어 경미상 가능성이 중심입니다.")
    if "살짝 베일" in src or "종이" in src:
        reasons.append("종이 모서리 등 경미한 베임 가능성으로 경미상에 해당합니다.")
    return PredictedSeverity(
        grade="E",
        label=_GRADE_LABELS["E"],
        is_actual_damage=False,
        confidence="high",
        prediction_reason=reasons or ["경미상 가능성 중심으로 실질적 중상/근무 제한 단서가 없습니다."],
        why_not_higher=_WHY_NOT_HIGHER_E,
        why_not_lower=_WHY_NOT_LOWER_E,
        missing_information=[],
        validation_warnings=[],
    )


def _unknown_result() -> PredictedSeverity:
    return PredictedSeverity(
        grade=None,
        label=_GRADE_LABELS[None],
        is_actual_damage=False,
        confidence="low",
        prediction_reason=["사고유형과 사용장비가 불명확해 예상 피해등급을 확정하기 어렵습니다."],
        why_not_higher="",
        why_not_lower="",
        missing_information=["사고유형", "사용장비", "노출 인원", "피해 부위"],
        validation_warnings=["정보 부족으로 등급 확정 불가"],
    )
