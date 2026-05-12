import json
import os
import re
from pathlib import Path
from typing import Any

from openai import OpenAI
from dotenv import load_dotenv

from models.schemas import AnalyzeMeta, NormalizeRequest, NormalizedInput, PreventionItem, SimilarCase
from services.classification_rules import build_rule_hints
from services.taxonomy import map_user_label

ACCIDENT_TYPES = [
    "끼임",
    "추락",
    "낙상",
    "충격",
    "교통",
    "화재·화상",
    "절단·베임",
    "폭발·파열",
    "감전",
    "과부하·온열",
    "질식·익사",
    "기타",
]

HAZARD_MAJOR_CATEGORIES = [
    "장비요인",
    "보호구요인",
    "환경요인",
    "인적요인",
    "절차요인",
    "통제요인",
    "숙련도요인",
    "정비요인",
    "기상요인",
    "작업환경요인",
    "기타",
]

HAZARD_MIDDLE_CATEGORIES = [
    "보호장비미착용",
    "사전점검미흡",
    "작업통제부족",
    "숙련도부족",
    "미끄럼/지면불량",
    "차량운행위험",
    "고소작업위험",
    "단독작업",
    "야간/조도불량",
    "장비노후화",
    "장비결함",
    "부품이탈",
    "낙하물",
    "환기부족",
    "확인미흡",
    "안전수칙미준수",
    "기타",
]

WORK_TYPES = [
    "차량운전·이동",
    "장비점검·정비",
    "운반작업",
    "훈련·사격",
    "취사",
    "공사·보수",
    "체력단련",
    "기타",
]

ENVIRONMENT_FACTORS = [
    "야간/조도불량",
    "우천/강설",
    "고소작업환경",
    "협소공간",
    "미끄럼/지면불량",
    "고온/저온",
    "환기부족",
    "해당 없음",
    "기타",
]

HUMAN_FACTORS = [
    "확인미흡",
    "숙련도부족",
    "부주의",
    "안전수칙미준수",
    "무리한작업",
    "단독작업",
    "해당 없음",
    "기타",
]

STANDARD_EQUIPMENT_VALUES = [
    "차량·트럭",
    "총기류",
    "크레인·지게차",
    "조리기구",
    "전동공구·절단기",
    "해당 없음",
    "기타",
]

MISSING_INFO_FIELDS = [
    "accident_type",
    "work_type",
    "hazard",
    "environment_factor",
    "human_factor",
    "equipment",
    "occurred_location",
    "occurred_at",
    "기타",
]

AI_RECOMMENDATIONS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "accident_type": {"type": "array", "items": {"type": "string", "enum": ACCIDENT_TYPES}},
        "work_type": {"type": "array", "items": {"type": "string", "enum": WORK_TYPES}},
        "hazard": {"type": "array", "items": {"type": "string", "enum": HAZARD_MIDDLE_CATEGORIES}},
        "environment_factors": {"type": "array", "items": {"type": "string", "enum": ENVIRONMENT_FACTORS}},
        "human_factors": {"type": "array", "items": {"type": "string", "enum": HUMAN_FACTORS}},
        "equipment": {"type": "array", "items": {"type": "string", "enum": STANDARD_EQUIPMENT_VALUES}},
        "hazard_raw_matched": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": [
        "accident_type",
        "work_type",
        "hazard",
        "environment_factors",
        "human_factors",
        "equipment",
        "hazard_raw_matched",
        "reason",
    ],
    "additionalProperties": False,
}

SECONDARY_HAZARD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "major": {"type": "string", "enum": HAZARD_MAJOR_CATEGORIES},
        "middle": {"type": "string", "enum": HAZARD_MIDDLE_CATEGORIES},
        "evidence": {"type": "string"},
    },
    "required": ["major", "middle", "evidence"],
    "additionalProperties": False,
}

MISSING_INFO_QUESTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "field": {"type": "string", "enum": MISSING_INFO_FIELDS},
        "question": {"type": "string"},
        "reason": {"type": "string"},
    },
    "required": ["field", "question", "reason"],
    "additionalProperties": False,
}

ANALYZE_LLM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "ranked_preventions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "prevention_id": {"type": "string"},
                    "priority": {"type": "integer"},
                    "recommended_reason": {"type": "string"},
                },
                "required": ["prevention_id", "priority", "recommended_reason"],
                "additionalProperties": False,
            },
        },
        "risk_reasons": {"type": "array", "items": {"type": "string"}},
        "action_guide": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "immediate_actions": {"type": "array", "items": {"type": "string"}},
                "follow_up_actions": {"type": "array", "items": {"type": "string"}},
                "expected_result_example": {"type": "string"},
            },
            "required": ["summary", "immediate_actions", "follow_up_actions", "expected_result_example"],
            "additionalProperties": False,
        },
    },
    "required": ["ranked_preventions", "risk_reasons", "action_guide"],
    "additionalProperties": False,
}

ANALYZE_SYSTEM_INSTRUCTION = """
당신은 군 안전관리 아차사고 분석 보조자입니다.
반드시 제공된 prevention_candidates 안에서만 예방대책을 선택하고 정렬하세요.
새 예방대책을 만들거나 DB 후보에 없는 prevention_id를 만들지 마세요.
prevention_id는 입력 후보의 prevention_id와 정확히 일치해야 합니다.
recommended_reason은 해당 후보가 normalized 사고 정보와 연결되는 이유만 설명하세요.
action_guide는 제공된 후보 content와 expected_action_result를 바탕으로 요약하세요.
risk_reasons는 위험도 판단 보조 설명만 작성하세요.
risk_score.score 또는 risk_score.level을 생성하거나 추정하지 마세요.
secondary_hazards와 raw_input은 근거로 참고하되, 원문에 없는 위험요인을 추가하지 마세요.
""".strip()

NORMALIZED_INPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "accident_type": {"type": "string", "enum": ACCIDENT_TYPES},
        "work_type": {"type": "string", "enum": WORK_TYPES},
        "hazard_major_category": {
            "type": "string",
            "enum": HAZARD_MAJOR_CATEGORIES,
            "description": "rule_hints.hazard_major_candidates를 우선 고려하되, generic한 인적요인/환경요인으로 과하게 쏠리지 않게 선택한다.",
        },
        "hazard_middle_category": {
            "type": "string",
            "enum": HAZARD_MIDDLE_CATEGORIES,
            "description": "반드시 표준 중분류 후보 중 하나만 사용한다. 세부 보호구명이나 설명형 문구는 쓰지 않는다.",
        },
        "environment_factors": {"type": "array", "items": {"type": "string", "enum": ENVIRONMENT_FACTORS}},
        "human_factors": {"type": "array", "items": {"type": "string", "enum": HUMAN_FACTORS}},
        "equipment": {
            "anyOf": [{"type": "string", "enum": STANDARD_EQUIPMENT_VALUES}, {"type": "null"}],
            "description": "반드시 표준 장비값 중 하나만 사용한다. 세부 장비명이나 설명형 값은 금지한다.",
        },
        "confidence": {"type": "number"},
        "ai_recommendations": AI_RECOMMENDATIONS_SCHEMA,
        "secondary_hazards": {"type": "array", "items": SECONDARY_HAZARD_SCHEMA},
        "missing_info_questions": {"type": "array", "items": MISSING_INFO_QUESTION_SCHEMA},
    },
    "required": [
        "accident_type",
        "work_type",
        "hazard_major_category",
        "hazard_middle_category",
        "environment_factors",
        "human_factors",
        "equipment",
        "confidence",
        "ai_recommendations",
        "secondary_hazards",
        "missing_info_questions",
    ],
    "additionalProperties": False,
}

SYSTEM_INSTRUCTION = """
당신은 군 안전관리 아차사고 입력을 표준 taxonomy로 정제하는 분류 엔진입니다.
반드시 JSON만 반환하세요. 설명, 마크다운, 코드블록을 출력하지 마세요.

사고유형 후보:
끼임, 추락, 낙상, 충격, 교통, 화재·화상, 절단·베임, 폭발·파열, 감전, 과부하·온열, 질식·익사, 기타

작업유형 허용값:
차량운전·이동, 장비점검·정비, 운반작업, 훈련·사격, 취사, 공사·보수, 체력단련, 기타
work_type에는 설명형 문장을 쓰지 말고 위 허용값 중 하나만 반환하세요.
예: "사격훈련 중 총기 부품 튕김"은 금지하고 "훈련·사격"으로 반환하세요.

위험요인_대분류 후보:
장비요인, 보호구요인, 환경요인, 인적요인, 절차요인, 통제요인, 숙련도요인, 정비요인, 기상요인, 작업환경요인, 기타

위험요인_중분류 예시:
보호장비미착용, 사전점검미흡, 작업통제부족, 숙련도부족, 미끄럼/지면불량, 차량운행위험,
고소작업위험, 단독작업, 야간/조도불량, 장비노후화, 확인미흡, 안전수칙미준수
위험요인_중분류는 반드시 위 표준 후보 또는 장비결함, 부품이탈, 낙하물, 환기부족, 기타 중 하나로만 반환하세요.

equipment 허용값:
차량·트럭, 총기류, 크레인·지게차, 조리기구, 전동공구·절단기, 해당 없음, 기타, null

ai_recommendations는 다음 구조로 반환하세요.
- accident_type: 사고유형 표준값 배열
- work_type: 작업유형 표준값 배열
- hazard: 위험요인 중분류 표준값 배열
- environment_factors: 환경요인 표준값 배열
- human_factors: 인적요인 표준값 배열
- equipment: 사용장비 표준값 배열
- hazard_raw_matched: 원문 또는 사용자 선택에서 매칭된 위험요인 근거
- reason: 추천 근거 설명
각 배열에는 프론트 칩에 있는 표준값만 넣고, 설명형 값은 reason에만 쓰세요.

primary hazard와 secondary_hazards 구분:
- primary hazard는 사고의 가장 직접적인 핵심 원인입니다. 기존 hazard_major_category와 hazard_middle_category에 넣으세요.
- secondary_hazards는 원문에 명시된 추가 위험요인입니다.
- 원문에 주요 위험요인 외의 추가 위험요인이 있으면 secondary_hazards에 major/middle/evidence로 구조화하세요.
- 원문에 없는 위험요인을 추정해서 secondary_hazards에 넣지 마세요.
- primary hazard와 같은 major/middle 조합은 secondary_hazards에 다시 넣지 마세요.

주변 통제 부족 처리:
- "주변 통제 부족", "통제 부족", "신호수 부재", "신호수 없이", "신호수는 없었습니다", "신호수가 없", "유도자 없", "감독 부재", "안전거리 미확보", "통제나 감독이 없었다"는 통제요인 / 작업통제부족으로 secondary_hazards에 포함하세요.
- 이 값은 human_factors에 억지로 넣지 마세요.
- 주변 통제 부족은 인적요인보다 통제요인이 우선입니다.
- 위험요인 추천값 ai_recommendations.hazard에는 "작업통제부족"을 포함할 수 있습니다.

차량 운행 + 신호수 부재 조합 처리:
- "신호수는 없었습니다", "신호수 없이", "신호수가 없", "유도자 없" 표현은 신호수 부재를 나타내며, 통제요인/작업통제부족을 primary 또는 secondary_hazards에 반드시 포함하세요.
- "후진", "사각지대", "치일", "들이받" 등 차량 위험 단서가 함께 있으면 통제요인/차량운행위험도 함께 반영하세요.
- 두 위험요인 중 하나를 primary로 선택하고 나머지는 secondary_hazards에 포함하세요.

고소작업 보호구 미착용 조합 처리:
- "안전벨트 없이", "안전대 없이", "안전벨트 미착용", "안전대 미착용"이 원문에 있으면 보호구요인/보호장비미착용을 primary hazard로 우선 선택하세요.
- 위 단서와 함께 "높은 곳", "고소작업", "건물 외벽", "사다리", "지붕", "난간" 단서가 있으면 작업환경요인/고소작업위험을 secondary_hazards에 추가하세요.
- environment_factors에 "고소작업환경"을 포함할 수 있습니다.

확인미흡 과추론 금지:
- 원문에 "확인하지 않았다", "확인을 안 했다", "점검하지 않았다", "확인 미흡" 같은 직접 단서가 없으면 "확인미흡"을 human_factors 또는 ai_recommendations.human_factors에 넣지 마세요.
- 단순히 사고가 발생할 뻔했다는 이유만으로 확인미흡을 추정하지 마세요.
- 사격훈련/보호안경/통제 부족 문장에서는 human_factors는 []가 적절합니다.

환경요인 처리:
- 환경요인은 야간/조도불량, 우천/강설, 고소작업환경, 협소공간, 미끄럼/지면불량, 고온/저온, 환기부족처럼 물리적·공간적·기상적 조건이 원문에 있을 때만 넣으세요.
- 원문에 환경 단서가 없으면 environment_factors는 [] 또는 ai_recommendations.environment_factors에 ["해당 없음"] 정도만 사용하세요.
- "주변 통제 부족"은 환경요인이 아닙니다.

추가 위험요인 예시:
- "사전점검 미흡", "작업 전 확인 미흡"은 절차요인 / 사전점검미흡 또는 확인미흡으로 secondary_hazards에 포함할 수 있습니다.
- "장비가 노후됨", "부품 이탈", "파손"은 장비요인 / 장비결함 또는 부품이탈로 secondary_hazards에 포함할 수 있습니다.
- "미끄러운 바닥", "물기", "젖은 계단"은 작업환경요인 / 미끄럼/지면불량으로 secondary_hazards에 포함할 수 있습니다.
- "야간", "어두움", "조도 부족"은 기상요인 / 야간/조도불량으로 secondary_hazards에 포함할 수 있습니다.

정보 부족 질문:
- 입력 정보가 부족하면 missing_info_questions에 추가 질문을 넣으세요.
- 충분한 정보가 있으면 missing_info_questions는 []로 두세요.
- 사고유형을 판단할 단서가 부족하면 field="accident_type" 질문을 넣으세요.
- 사용장비가 예방대책 추천에 중요하지만 원문에 없으면 field="equipment" 질문을 넣으세요.
- 위험요인이 불명확하면 field="hazard" 질문을 넣으세요.
- field는 accident_type, work_type, hazard, environment_factor, human_factor, equipment, occurred_location, occurred_at, 기타 중 하나를 사용하세요.

사용자가 선택한 칩은 참고하되, 상황 서술과 맞지 않으면 더 적절한 표준값을 선택하세요.
rule_hints.accident_type_candidates를 우선 고려하세요.
rule_hints.hazard_major_candidates가 있으면 인적요인/환경요인 같은 일반 범주보다 우선 고려하세요.
rule_hints.equipment_candidates가 있으면 그 표준 장비값을 우선 고려하세요.
rule_hints.excluded_accident_types에 포함된 사고유형은 선택하지 마세요.
상황 서술에 없는 위험을 추정하지 마세요.
"사격"이라는 단어만으로 화재·화상을 선택하지 마세요.
"부품 튐", "파편", "눈에 맞을 뻔함"은 충격을 우선 선택하세요.
보호안경/보호구 미착용이 핵심이면 보호구요인을 우선 선택하세요.
equipment에는 설명형 값을 쓰지 마세요.
"개인화기", "소총", "총기 부품", "탄피", "노리쇠"는 모두 "총기류"로 반환하세요.
"프라이팬", "칼", "냄비", "뜨거운 물", "기름"은 상황에 따라 "조리기구"로 반환하세요.
"그라인더", "드릴", "톱", "절단날", "절단기"는 "전동공구·절단기"로 반환하세요.
"차량", "트럭", "후진", "차륜"은 "차량·트럭"으로 반환하세요.
"지게차", "크레인", "인양장비"는 "크레인·지게차"로 반환하세요.
위 표준 장비군에 없으면 무리하게 세부 장비명을 만들지 말고 "기타" 또는 null을 사용하세요.
"폭발물", "신관", "회전체"처럼 현재 표준 장비군에 없는 값은 equipment에 세부명으로 쓰지 말고, 필요 시 "기타" 또는 null로 두세요.
명확한 장비 단서가 있으면 equipment를 null로 두지 말고 표준 장비명으로 채우되, 표준 장비군에 없는 단서만으로 과하게 추론하지 마세요.

위험요인 중분류 표준 표현:
- 보호안경, 장갑, 안전모 등 보호구 미착용은 세부 보호구명을 그대로 쓰지 말고 "보호장비미착용"을 우선 사용하세요.
- 선반, 상자, 적재물이 위에서 떨어져 맞을 뻔한 경우는 "낙하물"을 우선 사용하세요.
- 물기, 젖은 계단, 미끄러운 바닥은 "미끄럼/지면불량"을 우선 사용하세요.
- 신호수 부재, 후진 유도 부재, 주변 통제 미흡은 "작업통제부족"을 우선 사용하세요.
- 점검 없이 만짐, 작업 전 확인 부족은 "사전점검미흡" 또는 "확인미흡"을 우선 사용하세요.

위험요인 대분류 우선순위:
- 보호안경, 안전모, 장갑, 보호구 미착용이 직접 원인이면 보호구요인을 선택하세요.
- 신호수 부재, 안전거리 미확보, 주변 통제 미흡, 후진 유도 부재, 시야 사각지대 관리는 통제요인을 우선 고려하세요.
- 장비 결함, 부품 이탈, 볼트 튐, 파편 비산, 전선/누전, 밸브 이상, 회전체, 절단날 위험은 장비요인을 우선 고려하세요.
- 사전점검 미흡, 점검 없이 만짐, 안전수칙 미준수, 폭발물/탄약 취급 절차 문제는 절차요인을 우선 고려하세요.
- 물기, 젖은 계단, 장애물, 창고 적재물, 선반 낙하, 차량 위 작업, 밀폐공간, 환기 부족은 작업환경요인을 우선 고려하세요.
- 비, 눈, 결빙, 강풍, 폭염, 혹한, 야간 시야 제한처럼 기상이나 시간대가 직접 원인이면 기상요인을 선택하세요.
- 감전 상황에서 "젖은 손으로 콘센트를 만짐"은 기상요인보다 절차요인/인적요인/장비요인을 우선 고려하세요. 비나 눈 칩이 있어도 원문의 직접 원인이 접촉 행동이면 기상요인을 선택하지 마세요.
- 차량 문, 문틈, 회전체, 절단날처럼 장비의 물리적 구조에 끼이거나 닿는 위험은 통제요인보다 장비요인을 우선 고려하세요.
- 철판 모서리, 날카로운 모서리, 정리되지 않은 적재물처럼 현장 물체 배치나 표면이 직접 원인이면 인적요인보다 작업환경요인을 우선 고려하세요.
- 작업자가 등장한다는 이유만으로 인적요인을 선택하지 마세요. 방심, 무리한 운반, 혼자 작업처럼 사람의 행동이 핵심일 때만 인적요인을 선택하세요.
- 열, 불, 연기, 뜨거운 액체 등 물리적 환경 자체가 직접 원인이면 환경요인을 고려하되, 장비 고온부나 배기부 접촉은 장비요인도 함께 강하게 고려하세요.
탄피/파편 비산은 충격:
- 탄피, 파편, 비산물이 얼굴/눈/신체에 맞을 위험은 accident_type=충격입니다.
- 불, 열, 화염, 뜨거운 물질 없이 단순히 탄피나 파편이 튀는 상황에서 화재·화상을 선택하지 마세요.

지게차/크레인 + 충돌 위험:
- 지게차 또는 크레인이 보행자나 작업자와 충돌할 위험 → accident_type=교통, hazard_middle=차량운행위험
- 지게차는 equipment=크레인·지게차로 반환하세요.

밀폐공간 + 환기 부족:
- 밀폐된 공간 + 환기가 되지 않음 + 어지러움 → accident_type=질식·익사
- 폭염/탈진/열사병 단서 없이 어지러움만 있는 경우 과부하·온열을 선택하지 마세요.

선반/적재물 낙하는 충격:
- 선반이나 적재물이 아래 작업자 쪽으로 떨어질 위험 → accident_type=충격, hazard_middle=낙하물
- 낙상은 사람이 미끄러지거나 넘어지는 경우에만 사용하세요. 물체가 떨어지는 경우는 낙상이 아닙니다.

야간 + 조명/조도 부족:
- 야간 작업 중 조명 부족이나 조도 부족이 직접 원인 → hazard_major=기상요인, hazard_middle=야간/조도불량
- 바닥 장애물이 있어도 조도 문제가 직접 원인이면 기상요인을 작업환경요인보다 우선하세요.

회전부/회전체 정지 미확인 정비 작업:
- "회전부가 완전히 멈추지 않은 상태에서 손을 넣음", "회전체가 멈추지 않은 상태", "동작 중인 장비에 손을 넣음" 같은 단서는 절차요인/사전점검미흡입니다.
- 이 상황에서 작업통제부족(통제요인)을 선택하지 마세요. 작업통제부족은 신호수 부재, 감독 부재, 주변 통제 미흡처럼 외부 관리·감독이 없는 경우에만 사용합니다.
- hazard_middle은 "사전점검미흡" 또는 "안전수칙미준수"를 우선 사용하세요.

고온 장비 부위 접촉:
- "뜨거운 배기부", "배기관에 닿", "고온 부위 접촉" 등 고온 부품에 신체가 닿는 위험 → accident_type=화재·화상
- 이 경우 과부하·온열(근골격/온열질환)을 선택하지 마세요. 과부하·온열은 무거운 물체 운반, 장시간 폭염 작업에만 사용합니다.

단, 원문 근거가 부족하면 confidence를 낮추세요.
confidence는 0부터 1 사이 숫자로 산정하세요.
""".strip()


def mock_normalize(request: NormalizeRequest) -> NormalizedInput:
    rule_hints = build_rule_hints(request.situation_text, request.fields)
    accident_raw = request.fields.accident_type_raw or request.situation_text
    work_raw = request.fields.work_type_raw or "일반작업"
    hazard_raw = request.fields.hazard_raw
    environment_raw = request.fields.environment_factor_raw
    human_raw = request.fields.human_factor_raw
    hazard_middle_source = [
        *(request.fields.hazard_raw or []),
        *(request.fields.environment_factor_raw or []),
        *(request.fields.human_factor_raw or []),
    ] or [request.situation_text]

    accident_type = _first_hint(rule_hints, "accident_type_candidates") or _to_korean_taxonomy(
        map_user_label(accident_raw),
        default=accident_raw,
    )
    hazard_major = _first_hint(rule_hints, "hazard_major_candidates") or _infer_mock_hazard_major(hazard_raw)
    hazard_middle = _infer_mock_hazard_middle(hazard_middle_source)
    work_type = _standard_work_type(work_raw, request.situation_text)
    equipment = _standard_equipment(request.fields.equipment_raw or _first_hint(rule_hints, "equipment_candidates"))
    environment_factors = [_standard_environment_factor(value) for value in environment_raw]
    human_factors = [
        factor
        for value in human_raw
        if (factor := _standard_human_factor(value, allow_confirm_inference=True)) != "해당 없음"
    ]
    hazard_recommendations = _mock_hazard_recommendations(hazard_middle_source, hazard_middle)
    equipment_recommendations = [equipment] if equipment else []
    source_text = _source_text(request)
    secondary_hazards = _infer_secondary_hazards(source_text, hazard_major, hazard_middle)
    missing_info_questions = _infer_missing_info_questions(request, rule_hints, hazard_raw)

    return NormalizedInput(
        accident_type=accident_type,
        work_type=work_type,
        hazard_major_category=hazard_major,
        hazard_middle_category=hazard_middle,
        environment_factors=environment_factors,
        human_factors=human_factors,
        equipment=equipment,
        confidence=0.91,
        ai_recommendations={
            "accident_type": [accident_type] if accident_type in ACCIDENT_TYPES else [],
            "work_type": [work_type],
            "hazard": hazard_recommendations,
            "environment_factors": [value for value in environment_factors if value in ENVIRONMENT_FACTORS],
            "human_factors": [value for value in human_factors if value in HUMAN_FACTORS],
            "equipment": equipment_recommendations,
            "hazard_raw_matched": ", ".join(hazard_raw) if hazard_raw else "",
            "reason": str(rule_hints["rule_reason"]),
        },
        secondary_hazards=secondary_hazards,
        missing_info_questions=missing_info_questions,
    )


def normalize_with_llm(request: NormalizeRequest) -> NormalizedInput:
    _load_backend_env_if_needed()

    if os.getenv("LLM_PROVIDER", "openai").lower() != "openai":
        return mock_normalize(request)

    if not os.getenv("OPENAI_API_KEY"):
        return mock_normalize(request)

    try:
        response = _create_openai_response(request)
        payload = _parse_json_payload(_extract_response_text(response))
        payload["confidence"] = _clamp_confidence(payload.get("confidence"))
        payload = _sanitize_normalized_payload(payload, request)
        return NormalizedInput.model_validate(payload)
    except Exception:
        return mock_normalize(request)


def analyze_with_llm(
    normalized: NormalizedInput,
    prevention_candidates: list[PreventionItem],
    similar_cases: list[SimilarCase],
    meta: AnalyzeMeta,
    raw_input: str | None = None,
) -> dict[str, Any] | None:
    _load_backend_env_if_needed()

    if os.getenv("LLM_PROVIDER", "openai").lower() != "openai":
        return None
    if not os.getenv("OPENAI_API_KEY"):
        return None
    if not prevention_candidates:
        return None

    candidate_ids = {item.prevention_id for item in prevention_candidates}
    try:
        response = _create_analyze_openai_response(
            normalized=normalized,
            prevention_candidates=prevention_candidates,
            similar_cases=similar_cases,
            meta=meta,
            raw_input=raw_input,
        )
        payload = _parse_json_payload(_extract_response_text(response))
        ranked = [
            item
            for item in payload.get("ranked_preventions", [])
            if isinstance(item, dict) and item.get("prevention_id") in candidate_ids
        ]
        if not ranked:
            return None
        payload["ranked_preventions"] = ranked
        payload["risk_reasons"] = [
            str(value).strip() for value in payload.get("risk_reasons", []) if str(value).strip()
        ]
        return payload
    except Exception:
        return None


def _create_analyze_openai_response(
    normalized: NormalizedInput,
    prevention_candidates: list[PreventionItem],
    similar_cases: list[SimilarCase],
    meta: AnalyzeMeta,
    raw_input: str | None,
) -> Any:
    client = OpenAI()
    model = os.getenv("LLM_MODEL", "gpt-5.4-nano")
    user_payload = {
        "normalized": {
            "accident_type": normalized.accident_type,
            "work_type": normalized.work_type,
            "hazard_major_category": normalized.hazard_major_category,
            "hazard_middle_category": normalized.hazard_middle_category,
            "secondary_hazards": [item.model_dump() for item in normalized.secondary_hazards],
            "environment_factors": normalized.environment_factors,
            "human_factors": normalized.human_factors,
            "equipment": normalized.equipment,
            "confidence": normalized.confidence,
            "ai_recommendations_reason": normalized.ai_recommendations.reason,
        },
        "meta": meta.model_dump(),
        "raw_input": raw_input,
        "prevention_candidates": [
            {
                "prevention_id": item.prevention_id,
                "major_category": item.major_category,
                "middle_category": item.middle_category,
                "content": item.content,
                "expected_action_result": item.expected_action_result,
                "priority": item.priority,
            }
            for item in prevention_candidates
        ],
        "similar_cases": [item.model_dump() for item in similar_cases],
    }

    return client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": ANALYZE_SYSTEM_INSTRUCTION},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "analyze_candidate_ranking",
                "strict": True,
                "schema": ANALYZE_LLM_SCHEMA,
            }
        },
        max_output_tokens=1400,
        temperature=0,
    )


def _create_openai_response(request: NormalizeRequest) -> Any:
    client = OpenAI()
    model = os.getenv("LLM_MODEL", "gpt-5.4-nano")
    user_payload = {
        "situation_text": request.situation_text,
        "fields": request.fields.model_dump(),
        "rule_hints": build_rule_hints(request.situation_text, request.fields),
    }

    return client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {
                "role": "user",
                "content": json.dumps(user_payload, ensure_ascii=False),
            },
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "normalized_incident",
                "strict": True,
                "schema": NORMALIZED_INPUT_SCHEMA,
            }
        },
        max_output_tokens=1200,
        temperature=0,
    )


def _extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text)

    chunks: list[str] = []
    for output_item in getattr(response, "output", []) or []:
        for content_item in getattr(output_item, "content", []) or []:
            text = getattr(content_item, "text", None)
            if text:
                chunks.append(str(text))

    return "\n".join(chunks)


def _parse_json_payload(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        payload = json.loads(match.group(0))

    if not isinstance(payload, dict):
        raise ValueError("LLM response JSON is not an object")

    return payload


def _clamp_confidence(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("confidence must be numeric") from exc

    return max(0.0, min(1.0, confidence))


def _load_backend_env_if_needed() -> None:
    if os.getenv("OPENAI_API_KEY") is not None:
        return
    env_path = Path(__file__).resolve().parents[1] / ".env"
    load_dotenv(env_path)


def _first_hint(rule_hints: dict[str, Any], key: str) -> str | None:
    values = rule_hints.get(key)
    if isinstance(values, list) and values:
        return str(values[0])
    return None


def _infer_mock_hazard_major(hazard_raw: list[str]) -> str:
    joined = " ".join(hazard_raw)
    if any(keyword in joined for keyword in ["보호", "보호구", "보호장비", "미착용", "안전모", "보호안경"]):
        return "보호구요인"
    if any(keyword in joined for keyword in ["통제", "감독", "신호수", "안전거리"]):
        return "통제요인"
    if any(keyword in joined for keyword in ["장비", "고장", "불량", "노후", "파손"]):
        return "장비요인"
    if any(keyword in joined for keyword in ["점검", "절차", "안전수칙", "확인"]):
        return "절차요인"
    return "기타"


def _infer_mock_hazard_middle(hazard_raw: list[str]) -> str:
    if not hazard_raw:
        return "보호장비미착용"

    mapped = _to_korean_taxonomy(map_user_label(hazard_raw[0]), default=hazard_raw[0])
    if mapped != hazard_raw[0]:
        return mapped

    joined = " ".join(hazard_raw)
    if any(keyword in joined for keyword in ["보호", "미착용", "보호안경", "보호구"]):
        return "보호장비미착용"
    if "점검" in joined:
        return "사전점검미흡"
    if "통제" in joined or "감독" in joined:
        return "작업통제부족"
    if "미끄" in joined or "물기" in joined:
        return "미끄럼/지면불량"
    if "단독" in joined or "혼자" in joined:
        return "단독작업"
    return mapped


def _mock_hazard_recommendations(raw_values: list[str], primary: str) -> list[str]:
    recommendations = [primary] if primary in HAZARD_MIDDLE_CATEGORIES else []
    joined = " ".join(raw_values)
    if any(keyword in joined for keyword in ["통제", "감독", "신호수", "안전거리"]):
        recommendations.append("작업통제부족")
    if any(keyword in joined for keyword in ["보호", "미착용", "보호안경", "보호구"]):
        recommendations.append("보호장비미착용")
    return _dedupe_standard(recommendations, HAZARD_MIDDLE_CATEGORIES)


def _source_text(request: NormalizeRequest) -> str:
    return " ".join(
        [
            request.situation_text,
            request.fields.accident_type_raw or "",
            request.fields.work_type_raw or "",
            request.fields.equipment_raw or "",
            *request.fields.hazard_raw,
            *request.fields.environment_factor_raw,
            *request.fields.human_factor_raw,
        ]
    )


def _sanitize_normalized_payload(payload: dict[str, Any], request: NormalizeRequest) -> dict[str, Any]:
    source_text = _source_text(request)
    explicit_equipment = request.fields.equipment_raw or _first_hint(
        build_rule_hints(request.situation_text, request.fields),
        "equipment_candidates",
    )

    if any(keyword in source_text for keyword in ["사다리", "높은 곳", "차량 위", "고소작업"]) and any(
        keyword in source_text for keyword in ["떨어", "추락", "아래로"]
    ):
        payload["accident_type"] = "추락"

    if any(kw in source_text for kw in ["탄피", "파편", "비산"]) and not any(
        kw in source_text for kw in ["화상", "뜨거운", "불", "화염"]
    ):
        if payload.get("accident_type") == "화재·화상":
            payload["accident_type"] = "충격"

    if any(kw in source_text for kw in ["지게차", "크레인"]) and any(
        kw in source_text for kw in ["충돌", "보행자", "치일"]
    ):
        payload["accident_type"] = "교통"
        payload["hazard_major_category"] = "통제요인"
        payload["hazard_middle_category"] = "차량운행위험"

    if any(kw in source_text for kw in ["밀폐", "맨홀", "정화조"]) and any(
        kw in source_text for kw in ["환기", "산소 부족"]
    ):
        if payload.get("accident_type") == "과부하·온열":
            payload["accident_type"] = "질식·익사"

    if any(kw in source_text for kw in ["선반", "물자가"]) and "아래 작업자" in source_text:
        if payload.get("accident_type") in ["낙상", "추락"]:
            payload["accident_type"] = "충격"

    if any(kw in source_text for kw in ["야간", "밤"]) and any(kw in source_text for kw in ["조명", "조도"]):
        payload["hazard_major_category"] = "기상요인"
        payload["hazard_middle_category"] = "야간/조도불량"

    if any(kw in source_text for kw in ["회전부", "회전체가 완전히 멈추지 않", "멈추지 않은 상태에서 손"]) and any(
        kw in source_text for kw in ["끼일", "끼임", "손을 넣"]
    ):
        if payload.get("hazard_middle_category") == "작업통제부족":
            payload["hazard_major_category"] = "절차요인"
            payload["hazard_middle_category"] = "사전점검미흡"

    if any(kw in source_text for kw in ["배기부", "배기관"]) and any(
        kw in source_text for kw in ["뜨거운", "고온", "접촉", "닿"]
    ):
        if payload.get("accident_type") == "과부하·온열":
            payload["accident_type"] = "화재·화상"

    payload["work_type"] = _standard_work_type(str(payload.get("work_type") or ""), "")
    payload["equipment"] = _standard_equipment(payload.get("equipment"))
    if payload["equipment"] == "기타" and _standard_equipment(explicit_equipment) is None:
        payload["equipment"] = None
    payload["environment_factors"] = [
        _standard_environment_factor(str(value)) for value in payload.get("environment_factors", [])
    ]
    payload["human_factors"] = [
        value
        for value in (
            _standard_human_factor(str(item), allow_confirm_inference=_has_confirm_evidence(source_text))
            for item in payload.get("human_factors", [])
        )
        if value != "해당 없음"
    ]

    recommendations = payload.get("ai_recommendations")
    if not isinstance(recommendations, dict):
        recommendations = {}

    payload["ai_recommendations"] = {
        "accident_type": _standard_array(recommendations.get("accident_type"), ACCIDENT_TYPES),
        "work_type": _dedupe_standard(
            [_standard_work_type(str(value)) for value in _as_list(recommendations.get("work_type"))],
            WORK_TYPES,
        ),
        "hazard": _standard_array(recommendations.get("hazard"), HAZARD_MIDDLE_CATEGORIES),
        "environment_factors": _standard_array(recommendations.get("environment_factors"), ENVIRONMENT_FACTORS),
        "human_factors": _standard_human_array(recommendations.get("human_factors"), source_text),
        "equipment": _dedupe_standard(
            [
                equipment
                for value in _as_list(recommendations.get("equipment"))
                if (equipment := _standard_equipment(value)) is not None
            ],
            STANDARD_EQUIPMENT_VALUES,
        ),
        "hazard_raw_matched": str(recommendations.get("hazard_raw_matched") or ""),
        "reason": str(recommendations.get("reason") or ""),
    }

    if not payload["ai_recommendations"]["accident_type"] and payload.get("accident_type") in ACCIDENT_TYPES:
        payload["ai_recommendations"]["accident_type"] = [payload["accident_type"]]
    if not payload["ai_recommendations"]["work_type"]:
        payload["ai_recommendations"]["work_type"] = [payload["work_type"]]
    if not payload["ai_recommendations"]["hazard"] and payload.get("hazard_middle_category") in HAZARD_MIDDLE_CATEGORIES:
        payload["ai_recommendations"]["hazard"] = [payload["hazard_middle_category"]]
    if any(keyword in source_text for keyword in ["통제", "감독", "신호수", "안전거리"]) and "작업통제부족" not in payload[
        "ai_recommendations"
    ]["hazard"]:
        payload["ai_recommendations"]["hazard"].append("작업통제부족")
    if not payload["ai_recommendations"]["equipment"] and payload.get("equipment") in STANDARD_EQUIPMENT_VALUES:
        payload["ai_recommendations"]["equipment"] = [payload["equipment"]]
    if payload.get("equipment") is None:
        payload["ai_recommendations"]["equipment"] = []
    payload["secondary_hazards"] = _sanitize_secondary_hazards(
        payload.get("secondary_hazards"),
        source_text,
        str(payload.get("hazard_major_category") or ""),
        str(payload.get("hazard_middle_category") or ""),
    )
    payload["missing_info_questions"] = _sanitize_missing_info_questions(
        payload.get("missing_info_questions"),
        request,
        build_rule_hints(request.situation_text, request.fields),
    )
    return payload


def _sanitize_secondary_hazards(
    value: Any,
    source_text: str,
    primary_major: str,
    primary_middle: str,
) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        major = str(item.get("major") or "")
        middle = str(item.get("middle") or "")
        evidence = str(item.get("evidence") or "").strip()
        _append_secondary_hazard(result, major, middle, evidence, primary_major, primary_middle)

    for inferred in _infer_secondary_hazards(source_text, primary_major, primary_middle):
        _append_secondary_hazard(
            result,
            inferred["major"],
            inferred["middle"],
            inferred["evidence"],
            primary_major,
            primary_middle,
        )
    return result


def _append_secondary_hazard(
    result: list[dict[str, str]],
    major: str,
    middle: str,
    evidence: str,
    primary_major: str,
    primary_middle: str,
) -> None:
    if major not in HAZARD_MAJOR_CATEGORIES or middle not in HAZARD_MIDDLE_CATEGORIES:
        return
    if major == primary_major and middle == primary_middle:
        return
    if not evidence:
        return
    if any(item["major"] == major and item["middle"] == middle for item in result):
        return
    result.append({"major": major, "middle": middle, "evidence": evidence})


def _infer_secondary_hazards(source_text: str, primary_major: str, primary_middle: str) -> list[dict[str, str]]:
    hazards: list[dict[str, str]] = []
    if _has_control_evidence(source_text):
        _append_secondary_hazard(
            hazards,
            "통제요인",
            "작업통제부족",
            _evidence_or_default(source_text, ["주변 통제", "통제 부족", "신호수", "감독", "안전거리"], "원문 또는 입력 필드에서 통제 부족 단서가 확인됨"),
            primary_major,
            primary_middle,
        )
    if any(keyword in source_text for keyword in ["부품 이탈", "부품이탈", "부품이 튕", "부품 튕", "파손"]):
        _append_secondary_hazard(
            hazards,
            "장비요인",
            "부품이탈" if "부품" in source_text else "장비결함",
            _evidence_or_default(source_text, ["부품", "파손"], "원문에서 장비 또는 부품 이상 단서가 확인됨"),
            primary_major,
            primary_middle,
        )
    if any(keyword in source_text for keyword in ["사전점검", "점검 없이", "작업 전 확인 미흡"]):
        _append_secondary_hazard(
            hazards,
            "절차요인",
            "사전점검미흡",
            _evidence_or_default(source_text, ["사전점검", "점검 없이", "작업 전 확인"], "원문에서 사전점검 미흡 단서가 확인됨"),
            primary_major,
            primary_middle,
        )
    if any(keyword in source_text for keyword in ["물기", "미끄러운 바닥", "젖은 계단"]):
        _append_secondary_hazard(
            hazards,
            "작업환경요인",
            "미끄럼/지면불량",
            _evidence_or_default(source_text, ["물기", "미끄러운", "젖은 계단"], "원문에서 미끄럼 또는 지면 불량 단서가 확인됨"),
            primary_major,
            primary_middle,
        )
    if any(keyword in source_text for keyword in ["야간", "어두움", "어두워", "조도 부족"]):
        _append_secondary_hazard(
            hazards,
            "기상요인",
            "야간/조도불량",
            _evidence_or_default(source_text, ["야간", "어두", "조도"], "원문에서 야간 또는 조도 불량 단서가 확인됨"),
            primary_major,
            primary_middle,
        )
    if any(keyword in source_text for keyword in ["높은 곳", "고소작업", "건물 외벽", "사다리", "지붕", "난간", "작업발판"]):
        _append_secondary_hazard(
            hazards,
            "작업환경요인",
            "고소작업위험",
            _evidence_or_default(
                source_text,
                ["높은 곳", "고소작업", "건물 외벽", "사다리", "지붕", "난간"],
                "원문에서 고소작업 단서가 확인됨",
            ),
            primary_major,
            primary_middle,
        )
    if any(keyword in source_text for keyword in ["후진", "사각지대", "치일", "들이받", "지게차", "크레인"]):
        _append_secondary_hazard(
            hazards,
            "통제요인",
            "차량운행위험",
            _evidence_or_default(
                source_text,
                ["후진", "사각지대", "치일", "들이받", "지게차", "크레인"],
                "원문에서 차량 운행 위험 단서가 확인됨",
            ),
            primary_major,
            primary_middle,
        )
    return hazards


def _sanitize_missing_info_questions(
    value: Any,
    request: NormalizeRequest,
    rule_hints: dict[str, Any],
) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field") or "기타")
        if field not in MISSING_INFO_FIELDS:
            field = "기타"
        question = str(item.get("question") or "").strip()
        reason = str(item.get("reason") or "").strip()
        if question and not any(existing["field"] == field and existing["question"] == question for existing in result):
            result.append({"field": field, "question": question, "reason": reason or "추가 정보가 필요합니다."})

    for inferred in _infer_missing_info_questions(request, rule_hints, request.fields.hazard_raw):
        if not any(existing["field"] == inferred["field"] for existing in result):
            result.append(inferred)
    return result


def _infer_missing_info_questions(
    request: NormalizeRequest,
    rule_hints: dict[str, Any],
    hazard_raw: list[str],
) -> list[dict[str, str]]:
    questions: list[dict[str, str]] = []
    text = request.situation_text.strip()
    accident_candidates = rule_hints.get("accident_type_candidates")
    equipment_candidates = rule_hints.get("equipment_candidates")
    hazard_candidates = rule_hints.get("hazard_major_candidates")

    if len(text) < 20 or not accident_candidates:
        questions.append(
            {
                "field": "accident_type",
                "question": "어떤 방식의 위험이었습니까? 끼임, 감전, 충격, 베임 중 어떤 상황에 가까웠습니까?",
                "reason": "사고 메커니즘이 명확하지 않습니다.",
            }
        )
    if not equipment_candidates and any(keyword in text for keyword in ["정비", "작업", "훈련", "운반", "취급"]):
        questions.append(
            {
                "field": "equipment",
                "question": "어떤 장비 또는 물자를 사용하거나 취급 중이었습니까?",
                "reason": "사용장비 정보가 예방대책 추천에 필요합니다.",
            }
        )
    if not hazard_raw and (len(text) < 20 or not hazard_candidates):
        questions.append(
            {
                "field": "hazard",
                "question": "위험을 키운 원인은 무엇이었습니까? 보호장비, 통제, 점검, 지면 상태 중 해당하는 단서가 있습니까?",
                "reason": "위험요인이 명확하지 않습니다.",
            }
        )
    return questions


def _has_control_evidence(source_text: str) -> bool:
    return any(
        keyword in source_text
        for keyword in [
            "주변 통제 부족",
            "통제 부족",
            "주변 통제가 부족",
            "통제나 감독이 없었다",
            "신호수 부재",
            "신호수 없이",
            "신호수는 없",
            "신호수가 없",
            "유도자 없",
            "감독 부재",
            "안전거리 미확보",
        ]
    )


def _has_confirm_evidence(source_text: str) -> bool:
    return any(keyword in source_text for keyword in ["확인하지 않았다", "확인을 안 했다", "점검하지 않았다", "확인 미흡"])


def _evidence_or_default(source_text: str, keywords: list[str], default: str) -> str:
    for keyword in keywords:
        index = source_text.find(keyword)
        if index >= 0:
            start = max(0, index - 16)
            end = min(len(source_text), index + len(keyword) + 24)
            return source_text[start:end].strip()
    return default


def _standard_human_array(value: Any, source_text: str) -> list[str]:
    allow_confirm = _has_confirm_evidence(source_text)
    return _dedupe_standard(
        [
            factor
            for item in _as_list(value)
            if (factor := _standard_human_factor(str(item), allow_confirm_inference=allow_confirm)) != "해당 없음"
        ],
        HUMAN_FACTORS,
    )


def _standard_array(value: Any, allowed: list[str]) -> list[str]:
    return _dedupe_standard([_to_korean_taxonomy(str(item), default=str(item)) for item in _as_list(value)], allowed)


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else ([value] if isinstance(value, str) else [])


def _dedupe_standard(values: list[str], allowed: list[str]) -> list[str]:
    result: list[str] = []
    allowed_set = set(allowed)
    for value in values:
        if value in allowed_set and value not in result:
            result.append(value)
    return result


def _standard_work_type(value: str, situation_text: str = "") -> str:
    joined = f"{value} {situation_text}"
    if any(keyword in joined for keyword in ["차량", "운전", "이동", "후진", "트럭"]):
        return "차량운전·이동"
    if any(keyword in joined for keyword in ["점검", "정비", "장비"]):
        return "장비점검·정비"
    if any(keyword in joined for keyword in ["운반", "옮기", "적재", "하역"]):
        return "운반작업"
    if any(keyword in joined for keyword in ["훈련", "사격", "개인화기", "총기", "탄약"]):
        return "훈련·사격"
    if any(keyword in joined for keyword in ["취사", "조리", "밥", "프라이팬", "냄비"]):
        return "취사"
    if any(keyword in joined for keyword in ["공사", "보수", "시설", "용접"]):
        return "공사·보수"
    if any(keyword in joined for keyword in ["체력", "단련", "운동"]):
        return "체력단련"
    return "기타"


def _standard_equipment(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    if text in STANDARD_EQUIPMENT_VALUES:
        return None if text == "해당 없음" else text
    if any(keyword in text for keyword in ["차량", "트럭", "후진", "차륜"]):
        return "차량·트럭"
    if any(keyword in text for keyword in ["총기", "개인화기", "소총", "탄피", "노리쇠"]):
        return "총기류"
    if any(keyword in text for keyword in ["크레인", "지게차", "인양"]):
        return "크레인·지게차"
    if any(keyword in text for keyword in ["조리", "프라이팬", "칼", "냄비", "기름"]):
        return "조리기구"
    if any(keyword in text for keyword in ["전동공구", "절단기", "절단날", "그라인더", "드릴", "톱"]):
        return "전동공구·절단기"
    return "기타" if text.strip() else None


def _standard_environment_factor(value: str) -> str:
    mapped = _to_korean_taxonomy(map_user_label(value), default=value)
    if mapped in ENVIRONMENT_FACTORS:
        return mapped
    if any(keyword in value for keyword in ["야간", "밤", "어두"]):
        return "야간/조도불량"
    if any(keyword in value for keyword in ["비", "눈", "우천", "강설"]):
        return "우천/강설"
    if any(keyword in value for keyword in ["높은", "고소", "사다리", "차량 위"]):
        return "고소작업환경"
    if any(keyword in value for keyword in ["좁", "협소", "밀폐"]):
        return "협소공간"
    if any(keyword in value for keyword in ["미끄", "물기", "지면", "바닥"]):
        return "미끄럼/지면불량"
    if any(keyword in value for keyword in ["고온", "저온", "추", "덥", "폭염", "혹한"]):
        return "고온/저온"
    if "환기" in value:
        return "환기부족"
    if "해당 없음" in value:
        return "해당 없음"
    return "기타"


def _standard_human_factor(value: str, allow_confirm_inference: bool = False) -> str:
    mapped = _to_korean_taxonomy(map_user_label(value), default=value)
    if mapped == "확인미흡" and not allow_confirm_inference:
        return "해당 없음"
    if mapped in HUMAN_FACTORS:
        return mapped
    if "확인" in value and allow_confirm_inference:
        return "확인미흡"
    if any(keyword in value for keyword in ["숙련", "익숙"]):
        return "숙련도부족"
    if any(keyword in value for keyword in ["부주의", "방심"]):
        return "부주의"
    if "안전수칙" in value:
        return "안전수칙미준수"
    if "무리" in value:
        return "무리한작업"
    if any(keyword in value for keyword in ["단독", "혼자"]):
        return "단독작업"
    if "해당 없음" in value:
        return "해당 없음"
    return "기타"


def _to_korean_taxonomy(value: str, default: str | None = None) -> str:
    mapping = {
        "strain": "과부하·온열",
        "slip": "낙상",
        "fall": "낙상",
        "fall_from_height": "추락",
        "traffic": "교통",
        "fire": "화재·화상",
        "cut": "절단·베임",
        "collision": "충격",
        "protective_equipment": "보호구요인",
        "protective_equipment_missing": "보호장비미착용",
        "pre_check_missing": "사전점검미흡",
        "working_alone": "단독작업",
        "work_control_missing": "작업통제부족",
        "equipment_defect": "장비노후화",
        "general_work": "기타",
        "other": "기타",
        "unknown": "기타",
        "야간": "야간/조도불량",
        "우천": "우천/강설",
        "고소작업": "고소작업환경",
        "미끄럼": "미끄럼/지면불량",
    }
    return mapping.get(value, default or value)
