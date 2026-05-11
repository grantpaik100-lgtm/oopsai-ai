from __future__ import annotations

from models.schemas import NormalizeFields

ACCIDENT_TYPE_RULES: dict[str, dict[str, list[str] | str]] = {
    "끼임": {
        "definition": "신체 일부가 장비, 차량, 문, 회전체, 적재물 사이에 끼이거나 협착될 위험",
        "positive_keywords": [
            "끼임",
            "끼일",
            "협착",
            "사이에",
            "손이 장비 사이",
            "말림",
            "말려",
            "압착",
            "문틈",
            "회전체",
            "말려 들어",
            "적재물 사이",
        ],
        "negative_keywords": ["화상", "감전", "베임"],
        "examples": ["정비 중 손이 장비 사이에 끼일 뻔함"],
    },
    "추락": {
        "definition": "높은 곳에서 아래로 떨어지는 위험",
        "positive_keywords": ["높은 곳", "사다리", "지붕", "차량 위", "고소작업", "난간", "떨어짐", "아래로 떨어질"],
        "negative_keywords": ["평지 미끄러짐"],
        "examples": ["사다리 위 작업 중 발을 헛디뎌 떨어질 뻔함"],
    },
    "낙상": {
        "definition": "같은 높이 또는 낮은 단차에서 미끄러지거나 걸려 넘어지는 위험",
        "positive_keywords": ["미끄러짐", "넘어짐", "넘어질", "걸려 넘어짐", "바닥", "복도", "계단에서 넘어짐"],
        "negative_keywords": ["높은 곳에서 떨어짐", "사다리에서 떨어짐"],
        "examples": ["복도 바닥 물기 때문에 미끄러져 넘어질 뻔함"],
    },
    "충격": {
        "definition": "물체, 장비, 부품, 파편 등이 신체에 부딪히거나 맞을 위험",
        "positive_keywords": [
            "부품 튐",
            "부품이 튐",
            "파편",
            "날아옴",
            "맞을 뻔",
            "부딪힘",
            "충돌",
            "낙하물",
            "떨어져",
            "눈에 맞을 뻔",
            "튕겨",
            "볼트",
            "상자",
            "얼굴에 맞",
            "팔에 맞",
            "머리에 맞",
        ],
        "negative_keywords": ["화상", "데임", "절단", "베임", "감전"],
        "examples": ["사격 중 총기 부품이 튕겨 눈에 맞을 뻔함"],
    },
    "교통": {
        "definition": "차량, 트럭, 장갑차, 후진, 운전, 이동 중 발생하는 사고 위험",
        "positive_keywords": ["차량", "트럭", "운전", "후진", "차륜", "교통", "이동 중 접촉", "사각지대", "치일"],
        "negative_keywords": ["보행 중 단순 미끄러짐"],
        "examples": ["차량 후진 중 보행자와 충돌할 뻔함"],
    },
    "화재·화상": {
        "definition": "불, 열, 화염, 고온물질, 뜨거운 액체, 폭발열 등으로 인한 화상 또는 화재 위험",
        "positive_keywords": [
            "불",
            "화염",
            "연기",
            "고온",
            "데임",
            "뜨거운",
            "끓는",
            "화상",
            "기름",
            "조리열",
            "엔진열",
            "배기부",
            "난방기",
        ],
        "negative_keywords": ["단순 사격", "단순 부품 튐", "파편만 튐", "총기 부품 튐"],
        "examples": ["취사 중 뜨거운 기름이 손에 튈 뻔함"],
    },
    "절단·베임": {
        "definition": "날카로운 물체, 절단기, 칼, 톱 등에 베이거나 절단될 위험",
        "positive_keywords": ["베임", "절단", "칼", "톱", "절단기", "날", "절단날", "모서리", "벨 뻔", "찔림"],
        "negative_keywords": ["둔탁한 충격"],
        "examples": ["절단기 작업 중 손가락이 베일 뻔함"],
    },
    "폭발·파열": {
        "definition": "폭발물, 압력, 신관, 탄약, 용기 파열 등으로 폭발 또는 파열 피해가 발생할 위험",
        "positive_keywords": ["폭발", "파열", "신관", "폭발물", "탄약", "압력", "압력 용기", "터질", "용기 파손"],
        "negative_keywords": ["단순 화상", "단순 미끄러짐"],
        "examples": ["폭발물 취급 중 신관 파손 위험을 발견함"],
    },
    "감전": {
        "definition": "전선, 전기설비, 누전, 피복 손상 등으로 전류에 접촉할 위험",
        "positive_keywords": ["감전", "전선", "전기", "누전", "피복 손상", "전류", "콘센트"],
        "negative_keywords": ["화상만", "기계적 충격"],
        "examples": ["전선 피복 손상 부위를 만질 뻔함"],
    },
    "과부하·온열": {
        "definition": "무리한 중량물 취급, 반복 작업, 폭염 등으로 근골격계 부담 또는 온열질환이 생길 위험",
        "positive_keywords": ["무거운", "허리", "중량물", "과부하", "온열", "폭염", "탈진", "어지러움", "장시간", "무리하게"],
        "negative_keywords": ["차량 충돌", "감전"],
        "examples": ["무거운 탄약 박스를 운반하다 허리를 다칠 뻔함"],
    },
    "질식·익사": {
        "definition": "밀폐공간, 환기 부족, 유해가스, 수중 작업 등으로 호흡 곤란 또는 익수 위험이 생기는 상황",
        "positive_keywords": ["질식", "익사", "밀폐공간", "정화조", "환기 부족", "유해가스", "산소 부족", "물에 빠짐", "수중 작업", "안전줄"],
        "negative_keywords": ["단순 미끄러짐", "단순 충격"],
        "examples": ["밀폐공간 작업 중 환기가 부족해 어지러움을 느낌"],
    },
    "기타": {
        "definition": "위 후보에 명확히 속하지 않는 위험",
        "positive_keywords": ["기타"],
        "negative_keywords": [],
        "examples": ["분류 기준에 명확히 맞지 않는 아차사고"],
    },
}

HAZARD_MAJOR_RULES: dict[str, list[str]] = {
    "보호구요인": ["보호안경", "안전모", "안전화", "장갑", "방탄모", "보호구", "보호장비", "미착용"],
    "통제요인": [
        "통제 부족",
        "감독 부재",
        "안전거리 미확보",
        "주변 통제 미흡",
        "신호수 부재",
        "신호수 없이",
        "사각지대",
        "유도 없이",
    ],
    "장비요인": [
        "장비 결함",
        "노후",
        "파손",
        "고장",
        "부품 이탈",
        "부품",
        "볼트",
        "파편",
        "불량",
        "작동부",
        "프레임",
        "전선",
        "피복 손상",
        "신관",
        "배기부",
        "밸브",
        "압력 용기",
        "절단날",
        "그라인더",
        "문틈",
        "차량 문",
        "회전체",
    ],
    "절차요인": [
        "사전점검 미흡",
        "점검 없이",
        "절차 미준수",
        "안전수칙 미준수",
        "작업 전 확인 미흡",
        "헛디뎌",
        "혼자 운반",
        "안전줄 없이",
        "탄약 취급",
        "폭발물 취급",
        "강한 충격",
        "젖은 손",
        "콘센트",
    ],
    "숙련도요인": ["미숙", "숙련도 부족", "처음 하는 작업", "익숙하지 않음"],
    "작업환경요인": [
        "물기",
        "젖은 계단",
        "미끄러운 바닥",
        "바닥",
        "장애물",
        "협소공간",
        "밀폐공간",
        "정화조",
        "환기 부족",
        "정리정돈 불량",
        "사다리",
        "선반",
        "창고",
        "적재물",
        "차량 위",
        "모서리",
        "날카로운 모서리",
        "철판 모서리",
    ],
    "기상요인": ["비", "눈", "결빙", "강풍", "폭염", "혹한", "야간 시야 제한", "야간", "어두워"],
    "환경요인": ["불", "화염", "연기", "고온", "뜨거운", "기름", "조리열", "엔진열"],
    "인적요인": ["무리하게", "혼자", "방심", "부주의"],
    "정비요인": ["정비", "전선", "피복 손상", "누전"],
}

EQUIPMENT_RULES: dict[str, list[str]] = {
    "총기류": ["사격", "총기", "소총", "개인화기", "탄피", "총열", "노리쇠", "총기 부품"],
    "차량·트럭": ["차량", "트럭", "후진", "운전", "차륜"],
    "크레인·지게차": ["크레인", "지게차", "인양", "인양장비"],
    "조리기구": ["취사", "조리", "칼", "뜨거운 물", "끓는 물", "냄비", "기름", "프라이팬"],
    "전동공구·절단기": ["전동공구", "절단기", "그라인더", "드릴", "톱", "절단날"],
}


def build_rule_hints(situation_text: str, fields: NormalizeFields) -> dict[str, list[str] | str]:
    text = _build_match_text(situation_text, fields)
    equipment_text = _build_equipment_match_text(situation_text, fields)
    accident_candidates: list[str] = []
    hazard_candidates: list[str] = []
    equipment_candidates: list[str] = []
    excluded_accident_types: list[str] = []
    reasons: list[str] = []

    for accident_type, rule in ACCIDENT_TYPE_RULES.items():
        positives = _matched_keywords(text, _as_list(rule["positive_keywords"]))
        negatives = _matched_keywords(text, _as_list(rule["negative_keywords"]))

        if positives:
            accident_candidates.append(accident_type)
            reasons.append(f"{accident_type}: positive keyword {', '.join(positives)}")
        elif negatives:
            excluded_accident_types.append(accident_type)
            reasons.append(f"{accident_type}: excluded by negative keyword {', '.join(negatives)}")

    for category, keywords in HAZARD_MAJOR_RULES.items():
        matches = _matched_keywords(text, keywords)
        if matches:
            hazard_candidates.append(category)
            reasons.append(f"{category}: keyword {', '.join(matches)}")

    for equipment, keywords in EQUIPMENT_RULES.items():
        matches = _matched_keywords(equipment_text, keywords)
        if matches:
            equipment_candidates.append(equipment)
            reasons.append(f"{equipment}: keyword {', '.join(matches)}")

    accident_candidates = _prioritize_accident_candidates(accident_candidates, text)

    return {
        "accident_type_candidates": _unique(accident_candidates),
        "hazard_major_candidates": _unique(hazard_candidates),
        "equipment_candidates": _unique(equipment_candidates),
        "excluded_accident_types": _unique(excluded_accident_types),
        "rule_reason": "; ".join(reasons) if reasons else "매칭된 분류 규칙 없음",
    }


def _build_match_text(situation_text: str, fields: NormalizeFields) -> str:
    parts = [
        situation_text,
        fields.accident_type_raw or "",
        fields.work_type_raw or "",
        fields.equipment_raw or "",
        *fields.hazard_raw,
        *fields.environment_factor_raw,
        *fields.human_factor_raw,
    ]
    return " ".join(parts).lower()


def _build_equipment_match_text(situation_text: str, fields: NormalizeFields) -> str:
    parts = [
        situation_text,
        fields.equipment_raw or "",
        *fields.hazard_raw,
    ]
    return " ".join(parts).lower()


def _matched_keywords(text: str, keywords: list[str]) -> list[str]:
    return [keyword for keyword in keywords if _keyword_matches(text, keyword)]


def _keyword_matches(text: str, keyword: str) -> bool:
    normalized = keyword.lower()
    if normalized == "비":
        return any(term in text for term in [" 비 ", "비가", "비나", "우천"])
    if normalized == "눈":
        return any(term in text for term in [" 눈 ", "눈이", "눈길", "강설"])
    return normalized in text


def _prioritize_accident_candidates(candidates: list[str], text: str) -> list[str]:
    prioritized = list(candidates)
    if "교통" in prioritized and any(keyword in text for keyword in ["차량", "트럭", "후진", "운전", "차륜"]):
        prioritized.remove("교통")
        prioritized.insert(0, "교통")
    if "과부하·온열" in prioritized and any(keyword in text for keyword in ["무거운", "허리", "중량물", "무리하게"]):
        prioritized.remove("과부하·온열")
        prioritized.insert(0, "과부하·온열")
    return prioritized


def _as_list(value: list[str] | str) -> list[str]:
    return value if isinstance(value, list) else [value]


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result
