export interface ScenarioExpected {
  accident_type?: string | string[];
  work_type?: string | string[];
  hazard_middle_category?: string | string[];
  equipment?: string | null;
  secondary_hazard_middle?: string[];
  has_missing_info_questions?: boolean;
  min_prevention_count?: number;
  expected_prevention_keywords?: string[];
  expected_action_guide_keywords?: string[];
}

export interface IncidentScenario {
  id: string;
  name: string;
  occurred_location: string;
  occurred_at?: string;
  situation_text: string;
  fields?: {
    accident_type_raw?: string | null;
    work_type_raw?: string | null;
    hazard_raw?: string[];
    environment_factor_raw?: string[];
    human_factor_raw?: string[];
    equipment_raw?: string | null;
  };
  tags?: string[];
  expected?: ScenarioExpected;
}

export const INCIDENT_SCENARIOS: IncidentScenario[] = [
  {
    id: "S001",
    name: "사격 중 총기 부품 튐",
    occurred_location: "사격장",
    situation_text:
      "사격훈련 중 총기 부품이 튕겨 눈을 다칠 뻔했습니다. 보호안경을 착용하지 않았고 주변 통제가 부족했습니다.",
    tags: ["정보충분", "고위험"],
    expected: {
      accident_type: "충격",
      work_type: "훈련·사격",
      hazard_middle_category: "보호장비미착용",
      equipment: "총기류",
      secondary_hazard_middle: ["작업통제부족"],
    },
  },
  {
    id: "S002",
    name: "정비 중 사고 날 뻔함",
    occurred_location: "정비고",
    situation_text: "정비 중 사고 날 뻔했습니다.",
    tags: ["정보부족"],
    expected: {
      has_missing_info_questions: true,
    },
  },
  {
    id: "S003",
    name: "정비 중 전선 피복 손상",
    occurred_location: "정비고",
    situation_text: "정비 중 전선 피복이 벗겨진 부위를 만질 뻔해 감전 위험이 있었습니다.",
    tags: ["정보충분", "감전"],
    expected: {
      accident_type: "감전",
    },
  },
  {
    id: "S004",
    name: "탄약 신관 충격 위험",
    occurred_location: "탄약고",
    situation_text: "탄약 박스를 옮기던 중 신관 부위가 충격을 받을 뻔했습니다.",
    tags: ["정보충분", "고위험", "폭발"],
    expected: {
      accident_type: "폭발·파열",
    },
  },
  {
    id: "S005",
    name: "복도 물기 낙상 위험",
    occurred_location: "생활관 복도",
    situation_text: "생활관 복도에 물기가 있어 지나가던 병사가 미끄러져 넘어질 뻔했습니다.",
    tags: ["정보충분", "경미", "낙상"],
    expected: {
      accident_type: "낙상",
      hazard_middle_category: "미끄럼/지면불량",
    },
  },
  {
    id: "S006",
    name: "차량 후진 신호수 부재",
    occurred_location: "차량 정비장",
    situation_text:
      "보급 트럭이 후진하다가 뒤쪽에서 작업하던 병사 2명을 못 보고 거의 들이받을 뻔했습니다. 신호수는 없었습니다.",
    tags: ["정보충분", "고위험", "차량"],
    expected: {
      accident_type: "교통",
      equipment: "차량·트럭",
      secondary_hazard_middle: ["차량운행위험"],
    },
  },
  {
    id: "S007",
    name: "고소작업 안전벨트 미착용",
    occurred_location: "건물 외벽",
    situation_text: "건물 외벽 보수 작업 중 병사가 안전벨트 없이 높은 곳에서 작업하고 있었습니다.",
    tags: ["정보충분", "고위험", "추락"],
    expected: {
      accident_type: "추락",
      hazard_middle_category: "보호장비미착용",
      secondary_hazard_middle: ["고소작업위험"],
    },
  },
  {
    id: "S008",
    name: "취사 중 기름 화상",
    occurred_location: "취사장",
    situation_text: "취사장에서 튀김 작업 중 뜨거운 기름이 손등에 튈 뻔했습니다.",
    tags: ["정보충분", "화재"],
    expected: {
      accident_type: "화재·화상",
      equipment: "조리기구",
    },
  },
  {
    id: "S009",
    name: "경미한 실내 걸림",
    occurred_location: "행정반",
    situation_text: "행정반에서 의자 다리에 발이 걸려 살짝 휘청였지만 넘어지지는 않았습니다.",
    tags: ["경미", "낙상"],
    expected: {
      accident_type: "낙상",
    },
  },
  {
    id: "S010",
    name: "매우 추상적 입력",
    occurred_location: "훈련장",
    situation_text: "훈련 중 위험했습니다. 다칠 뻔했습니다.",
    tags: ["정보부족"],
    expected: {
      has_missing_info_questions: true,
    },
  },
  {
    id: "S011",
    name: "장비 정비 중 손 끼임 위험",
    occurred_location: "정비고",
    situation_text:
      "정비 중 회전부가 완전히 멈추지 않은 상태에서 손을 넣었다가 손가락이 끼일 뻔했습니다.",
    tags: ["정보충분", "고위험"],
    expected: {
      accident_type: "끼임",
      work_type: "장비점검·정비",
      hazard_middle_category: ["사전점검미흡", "안전수칙미준수"],
    },
  },
  {
    id: "S012",
    name: "절단기 작업 중 손가락 베임 위험",
    occurred_location: "정비고",
    situation_text:
      "절단기 작업 중 보호장갑을 착용하지 않은 상태에서 손가락이 날에 닿을 뻔했습니다.",
    tags: ["정보충분", "고위험"],
    expected: {
      accident_type: "절단·베임",
      hazard_middle_category: "보호장비미착용",
      equipment: "전동공구·절단기",
    },
  },
  {
    id: "S013",
    name: "사다리 작업 중 발 헛디딤",
    occurred_location: "창고",
    situation_text: "창고 정리 중 사다리 위에서 발을 헛디뎌 떨어질 뻔했습니다.",
    tags: ["정보충분", "추락"],
    expected: {
      accident_type: "추락",
      hazard_middle_category: "고소작업위험",
    },
  },
  {
    id: "S014",
    name: "계단 이동 중 미끄러짐",
    occurred_location: "생활관 계단",
    situation_text: "비가 온 뒤 계단이 젖어 있어 내려가던 병사가 미끄러질 뻔했습니다.",
    tags: ["정보충분", "낙상"],
    expected: {
      accident_type: "낙상",
      hazard_middle_category: "미끄럼/지면불량",
    },
  },
  {
    id: "S015",
    name: "탄피 비산 안면 충격 위험",
    occurred_location: "사격장",
    situation_text:
      "사격 중 탄피가 얼굴 쪽으로 튀었고 보호안경을 착용하지 않아 다칠 뻔했습니다.",
    tags: ["정보충분", "고위험"],
    expected: {
      accident_type: "충격",
      work_type: "훈련·사격",
      hazard_middle_category: "보호장비미착용",
      equipment: "총기류",
    },
  },
  {
    id: "S016",
    name: "차량 정비 중 고임목 미설치",
    occurred_location: "차량 정비장",
    situation_text:
      "차량 정비 중 고임목을 설치하지 않아 차량이 움직일 뻔했습니다.",
    tags: ["정보충분", "차량"],
    expected: {
      accident_type: "교통",
      equipment: "차량·트럭",
      hazard_middle_category: ["사전점검미흡", "작업통제부족"],
    },
  },
  {
    id: "S017",
    name: "지게차 운반 중 보행자 충돌 위험",
    occurred_location: "물자창고",
    situation_text:
      "지게차가 물자를 운반하던 중 보행자를 보지 못해 충돌할 뻔했습니다.",
    tags: ["정보충분", "고위험", "차량"],
    expected: {
      accident_type: "교통",
      equipment: "크레인·지게차",
      hazard_middle_category: "차량운행위험",
    },
  },
  {
    id: "S018",
    name: "취사 중 뜨거운 물 화상 위험",
    occurred_location: "취사장",
    situation_text: "취사장에서 뜨거운 물통을 옮기다가 손에 쏟을 뻔했습니다.",
    tags: ["정보충분", "화재"],
    expected: {
      accident_type: "화재·화상",
      work_type: "취사",
      equipment: "조리기구",
    },
  },
  {
    id: "S019",
    name: "난방기 주변 가연물 화재 위험",
    occurred_location: "생활관",
    situation_text:
      "생활관 난방기 주변에 종이박스가 가까이 놓여 화재가 날 뻔했습니다.",
    tags: ["정보충분", "화재"],
    expected: {
      accident_type: "화재·화상",
      hazard_middle_category: ["안전수칙미준수", "작업통제부족"],
    },
  },
  {
    id: "S020",
    name: "폭발물 취급 중 낙하 위험",
    occurred_location: "탄약고",
    situation_text:
      "폭발물 취급 중 고정이 미흡해 바닥에 떨어질 뻔했습니다.",
    tags: ["정보충분", "고위험", "폭발"],
    expected: {
      accident_type: "폭발·파열",
      hazard_middle_category: ["안전수칙미준수", "사전점검미흡"],
    },
  },
  {
    id: "S021",
    name: "전원 미차단 정비 감전 위험",
    occurred_location: "정비고",
    situation_text:
      "전기장비 정비 중 전원을 차단하지 않고 커버를 열어 감전될 뻔했습니다.",
    tags: ["정보충분", "감전"],
    expected: {
      accident_type: "감전",
      work_type: "장비점검·정비",
      hazard_middle_category: ["안전수칙미준수", "사전점검미흡"],
    },
  },
  {
    id: "S022",
    name: "젖은 손으로 콘센트 접촉 위험",
    occurred_location: "생활관",
    situation_text:
      "젖은 손으로 콘센트 주변 전기장비를 만지려다 감전될 뻔했습니다.",
    tags: ["정보충분", "감전"],
    expected: {
      accident_type: "감전",
      hazard_middle_category: ["안전수칙미준수"],
    },
  },
  {
    id: "S023",
    name: "밀폐공간 환기 부족",
    occurred_location: "지하 시설",
    situation_text:
      "밀폐된 공간에서 작업 중 환기가 되지 않아 어지러움을 느꼈습니다.",
    tags: ["정보충분", "질식"],
    expected: {
      accident_type: "질식·익사",
      hazard_middle_category: "환기부족",
    },
  },
  {
    id: "S024",
    name: "맨홀 작업 중 단독작업",
    occurred_location: "맨홀 내부",
    situation_text:
      "맨홀 내부 확인 작업을 혼자 진행하다가 연락이 끊길 뻔했습니다.",
    tags: ["정보부족", "질식"],
    expected: {
      accident_type: ["질식·익사", "기타"],
      hazard_middle_category: "단독작업",
    },
  },
  {
    id: "S025",
    name: "무거운 탄약박스 단독 운반",
    occurred_location: "탄약고",
    situation_text:
      "무거운 탄약박스를 혼자 들다가 허리를 다칠 뻔했습니다.",
    tags: ["정보충분", "과부하"],
    expected: {
      accident_type: "과부하·온열",
      hazard_middle_category: ["안전수칙미준수", "단독작업"],
    },
  },
  {
    id: "S026",
    name: "폭염 속 장시간 제초작업",
    occurred_location: "연병장 주변",
    situation_text:
      "폭염 속에서 장시간 제초작업을 하다가 어지러움과 탈진 증상이 있었습니다.",
    tags: ["정보충분", "과부하"],
    expected: {
      accident_type: "과부하·온열",
    },
  },
  {
    id: "S027",
    name: "야간 작업 중 조도 부족",
    occurred_location: "야외 작업장",
    situation_text:
      "야간 작업 중 조명이 부족해 바닥 장애물을 보지 못하고 넘어질 뻔했습니다.",
    tags: ["정보충분", "낙상"],
    expected: {
      accident_type: "낙상",
      hazard_middle_category: "야간/조도불량",
    },
  },
  {
    id: "S028",
    name: "적재물 낙하 위험",
    occurred_location: "창고",
    situation_text:
      "창고 선반 위 물자가 제대로 고정되지 않아 아래 작업자 쪽으로 떨어질 뻔했습니다.",
    tags: ["정보충분"],
    expected: {
      accident_type: "충격",
      hazard_middle_category: "낙하물",
    },
  },
  {
    id: "S029",
    name: "보호구 착용 여부 불명확",
    occurred_location: "작업장",
    situation_text:
      "작업 중 위험한 상황이 있었지만 어떤 장비를 사용했는지와 보호구 착용 여부가 명확하지 않습니다.",
    tags: ["정보부족"],
    expected: {
      has_missing_info_questions: true,
    },
  },
  {
    id: "S030",
    name: "매우 추상적 신고",
    occurred_location: "작업장",
    situation_text: "작업 중 위험했습니다. 사고가 날 뻔했습니다.",
    tags: ["정보부족"],
    expected: {
      has_missing_info_questions: true,
    },
  },
];
