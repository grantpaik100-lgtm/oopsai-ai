# 군 아차사고 예방대책 AI 시스템

## 프로젝트 개요

군 아차사고(Near-Miss) 데이터를 기반으로 사용자가 위험 상황을 입력하면
AI가 예방대책을 추천하고, 조치결과까지 관리하는 풀스택 웹 앱.

\---

## 기술 스택

|구분|기술|
|-|-|
|프론트엔드|React + Vite + TypeScript + Tailwind CSS|
|백엔드|FastAPI (Python 3.11+)|
|LLM|Anthropic SDK (claude-sonnet-4-5)|
|데이터|SQLite (pandas로 xlsx → DB 변환)|
|패키지 관리|pnpm (프론트) / uv (백엔드)|

\---

## 디렉토리 구조

```
project/
├── CLAUDE.md
├── data/
│   └── 아차사고\_표준화\_3시트\_v2.xlsx   ← 기존 데이터
├── backend/
│   ├── main.py                          ← FastAPI 앱 진입점
│   ├── routers/
│   │   ├── analyze.py                   ← POST /api/analyze
│   │   ├── cases.py                     ← GET /api/cases/similar
│   │   └── admin.py                     ← 관리자 CRUD
│   ├── services/
│   │   ├── llm\_engine.py                ← LLM 정제 엔진
│   │   ├── taxonomy.py                  ← taxonomy 매핑 로직
│   │   └── db.py                        ← SQLite 연결
│   ├── models/
│   │   └── schemas.py                   ← Pydantic 모델
│   └── scripts/
│       └── init\_db.py                   ← xlsx → SQLite 변환
└── frontend/
    ├── src/
    │   ├── App.tsx
    │   ├── pages/
    │   │   ├── InputFlow.tsx             ← 입력 플로우 (s0\~s9)
    │   │   ├── MyReports.tsx             ← 내 신고 목록
    │   │   ├── ResultDetail.tsx          ← 결과 상세
    │   │   ├── ActionResult.tsx          ← 조치결과 입력
    │   │   └── admin/
    │   │       ├── AdminDashboard.tsx
    │   │       ├── ReviewQueue.tsx
    │   │       ├── CaseEditor.tsx
    │   │       └── Statistics.tsx
    │   ├── components/
    │   │   ├── ChipSelector.tsx
    │   │   ├── STTButton.tsx
    │   │   ├── AiBubble.tsx
    │   │   ├── ConfirmScreen.tsx
    │   │   └── ProgressBar.tsx
    │   ├── hooks/
    │   │   └── useSTT.ts                 ← Web Speech API
    │   └── api/
    │       └── client.ts                 ← API 호출 함수
    └── vite.config.ts
```

\---

## 데이터베이스 스키마

### init\_db.py 실행 시 xlsx → SQLite 자동 변환

```sql
-- 시트1: 사고 사례
CREATE TABLE incident\_cases (
  case\_id TEXT PRIMARY KEY,
  원문사례 TEXT,
  사고유형\_표준 TEXT,
  분류근거 TEXT,
  사례종류 TEXT,
  부대종류 TEXT,
  작업유형 TEXT,
  세부작업 TEXT,
  장소\_환경 TEXT,
  사용장비 TEXT,
  행동 TEXT,
  위험상황 TEXT,
  피해부위 TEXT,
  피해결과 TEXT,
  보호장비여부 TEXT,
  환경요인 TEXT,
  인적요인 TEXT,
  주요위험키워드 TEXT,
  status TEXT DEFAULT 'confirmed',  -- confirmed | pending
  created\_at DATETIME DEFAULT CURRENT\_TIMESTAMP
);

-- 시트2: 위험요인 taxonomy
CREATE TABLE hazard\_taxonomy (
  hazard\_id TEXT PRIMARY KEY,
  원문위험요인 TEXT,
  위험요인\_대분류 TEXT,
  위험요인\_중분류 TEXT,
  위험설명 TEXT,
  관련키워드 TEXT
);

-- 시트3: 예방대책 taxonomy
CREATE TABLE prevention\_taxonomy (
  prevention\_id TEXT PRIMARY KEY,
  원문예방대책 TEXT,
  예방대책\_대분류 TEXT,
  예방대책\_중분류 TEXT,
  적용상황 TEXT,
  기대효과 TEXT,
  관련키워드 TEXT
);

-- 신규 케이스 (사용자 입력 → 검수 대기)
CREATE TABLE pending\_cases (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  case\_id TEXT UNIQUE,
  raw\_input TEXT,          -- 사용자 원문 JSON
  normalized TEXT,         -- LLM 정제 결과 JSON
  output\_json TEXT,        -- 예방대책 출력 JSON
  조치결과 TEXT,
  조치일시 DATE,
  status TEXT DEFAULT 'pending',  -- pending | approved | rejected
  submitted\_by TEXT,
  submitted\_at DATETIME DEFAULT CURRENT\_TIMESTAMP,
  reviewed\_by TEXT,
  reviewed\_at DATETIME
);
```

\---

## API 명세

### POST /api/normalize

사용자 원문 입력 → LLM이 taxonomy 표준어로 변환

**Request:**

```json
{
  "situation\_text": "막사 앞 복도에서 물건 옮기다가 넘어졌어요",
  "fields": {
    "사고유형\_raw": "미끄러지거나 넘어졌다",
    "작업유형\_raw": "물건 옮기다가",
    "위험요인\_raw": \["보호장비를 안 했다", "혼자 작업했다"],
    "환경요인\_raw": \["경사지거나 미끄러웠다"],
    "인적요인\_raw": \["안전수칙을 무시했다"],
    "사용장비\_raw": "해당 없음"
  }
}
```

**Response:**

```json
{
  "사고유형": "낙상",
  "작업유형": "운반작업",
  "위험요인\_대분류": "보호구요인",
  "위험요인\_중분류": "보호장비미착용",
  "환경요인": \["미끄럼"],
  "인적요인": \["안전수칙미준수", "단독작업"],
  "사용장비": null,
  "신뢰도": 0.91,
  "ai\_recommendations": {
    "사고유형": "낙상",
    "위험요인\_raw\_matched": "보호장비를 안 했다"
  }
}
```

### POST /api/analyze

정제된 JSON → 예방대책 매핑 + 유사사례 검색

**Request:**

```json
{
  "normalized": { /\* /api/normalize 결과 \*/ },
  "meta": {
    "submitted\_by": "user\_001",
    "식별일시": "2026-05-11T10:30:00",
    "식별장소": "3중대 막사 앞 복도"
  }
}
```

**Response (출력 JSON):**

```json
{
  "meta": {
    "case\_id": "PENDING\_001",
    "timestamp": "2026-05-11T10:42:00",
    "status": "pending\_review"
  },
  "input\_summary": {
    "사고유형": "낙상",
    "작업유형": "운반작업",
    "위험요인": "보호구요인 / 보호장비미착용",
    "환경요인": "미끄럼",
    "인적요인": "안전수칙미준수, 단독작업",
    "사용장비": "해당없음",
    "식별일시": "2026-05-11T10:30:00",
    "식별장소": "3중대 막사 앞 복도"
  },
  "prevention\_list": \[
    {
      "prevention\_id": "PRV\_034",
      "대분류": "보호장비",
      "중분류": "안전화착용",
      "내용": "작업 전 안전화 착용 의무화",
      "예상\_조치결과": {
        "효과요약": "발 부상 위험 대폭 감소",
        "기대효과": "낙상 시 발목·족부 골절 예방",
        "적용상황": "고소·운반 작업 시"
      },
      "우선순위": 1
    }
  ],
  "similar\_cases": \[
    {
      "case\_id": "CASE\_005",
      "유사도": 0.94,
      "사고요약": "유류탱크 미끄러짐 낙상",
      "사고유형": "낙상"
    }
  ],
  "risk\_score": {
    "level": "중",
    "score": 62
  }
}
```

### GET /api/cases/similar?type=낙상\&hazard=보호구요인

유사 사례 검색 (TOP 3)

### GET /api/cases/pending

검수 대기 목록 (관리자용)

### PATCH /api/cases/{case\_id}/review

검수 승인/반려 (관리자용)

### PATCH /api/cases/{case\_id}/action-result

조치결과 입력

\---

## LLM 정제 엔진 (llm\_engine.py)

### 시스템 프롬프트

```
당신은 군 안전 전문가입니다.
사용자의 아차사고 입력을 아래 taxonomy 기준으로 분류해주세요.

사고유형 (하나만): 끼임 | 추락 | 낙상 | 충격 | 교통 | 화재·화상 | 절단·베임 | 폭발·파열 | 감전 | 과부하·온열 | 질식·익사 | 기타

위험요인\_대분류 (하나만): 장비요인 | 보호구요인 | 환경요인 | 인적요인 | 절차요인 | 통제요인 | 숙련도요인 | 정비요인 | 기상요인 | 작업환경요인 | 기타

위험요인\_중분류 예시: 보호장비미착용 | 사전점검미흡 | 작업통제부족 | 숙련도부족 | 미끄럼/지면불량 | 차량운행위험 | 고소작업위험 | 단독작업 | 야간/조도불량 | 장비노후화

반드시 JSON만 반환. 설명 불필요.
```

### 결과 JSON 스키마 (Pydantic)

```python
class NormalizedInput(BaseModel):
    사고유형: str
    작업유형: str
    위험요인\_대분류: str
    위험요인\_중분류: str
    환경요인: list\[str]
    인적요인: list\[str]
    사용장비: str | None
    신뢰도: float
```

\---

## 프론트엔드 화면 명세

### 입력 플로우 (InputFlow.tsx) — 10개 화면

|화면 ID|이름|설명|
|-|-|-|
|s0|AI 시작|상황 자유 서술 (STT + 텍스트) → AI 분석|
|s1|식별 정보|날짜·시간·장소 입력 (date picker + text)|
|s2|사고유형|1/6 단일 선택, AI 추천 칩 강조|
|s3|작업유형|2/6 단일 선택, AI 추천|
|s4|위험요인|3/6 다중 선택, AI 추천, STT 보조|
|s5|환경요인|4/6 다중 선택, AI 추천|
|s6|인적요인|5/6 다중 선택, AI 추천|
|s7|사용장비|6/6 단일 선택 + 직접 입력|
|s8|확인 화면|전체 입력 요약, 스크롤 없음, 수정 링크|
|s9|제출 완료|AI 예방대책 표시, 신고 목록 이동|

### 필수 필드 검증 규칙

```typescript
// 각 스텝에서 "다음" 클릭 시 검증
const REQUIRED\_STEPS = {
  s2: { field: 'accType',    msg: '사고유형을 선택해주세요' },
  s3: { field: 'workType',   msg: '작업유형을 선택해주세요' },
  s4: { field: 'hazard',     msg: '위험요인을 하나 이상 선택해주세요' },
  s5: { field: 'envFactor',  msg: '환경요인을 선택해주세요 (해당없음 선택 가능)' },
  s6: { field: 'humanFactor',msg: '인적요인을 선택해주세요 (해당없음 선택 가능)' },
  s7: { field: 'equipment',  msg: '사용장비를 선택해주세요 (해당없음 선택 가능)' },
}

// 검증 실패 시 UI
// 1. 칩 영역 테두리 → border-red-400 (1.5초 후 원복)
// 2. 칩 영역 아래 에러 메시지 표시
// 3. 다음 화면 이동 차단
```

### 확인 화면 (s8) 검증

```typescript
// 제출 전 미입력 항목 체크
// 미입력 행 → 주황색 배경 + "탭해서 입력하기" 버튼
// 미입력 항목 있으면 제출 버튼 비활성화
const isEmpty = (val: string | string\[]) =>
  !val || (Array.isArray(val) \&\& val.length === 0);
```

### ChipSelector 컴포넌트 인터페이스

```typescript
interface ChipSelectorProps {
  options: string\[];
  aiRecommended?: string\[];   // AI 추천 항목 (보라 테두리 + AI 배지)
  aiReason?: string;          // AI 추천 이유 (말풍선)
  multi?: boolean;            // 다중 선택 여부
  value: string\[];
  onChange: (val: string\[]) => void;
  error?: boolean;            // 검증 실패 시 빨간 테두리
  errorMsg?: string;
}
```

### STTButton 컴포넌트 (Web Speech API)

```typescript
// Web Speech API (SpeechRecognition)
// lang: 'ko-KR'
// 결과 → textarea에 자동 삽입
// 지원 안 되는 브라우저 → 버튼 비활성화 + 툴팁
```

\---

## 선택지 데이터 (프론트엔드 상수)

```typescript
export const CHIPS = {
  사고유형: \[
    '몸이 끼었다', '미끄러지거나 넘어졌다', '높은 곳에서 떨어졌다',
    '차량 관련 사고', '불에 데거나 화재', '날카로운 것에 베였다',
    '물체에 부딪혔다', '기타'
  ],
  작업유형: \[
    '차량 운전·이동 중', '장비 점검·정비 중', '물건 옮기다가',
    '훈련·사격 중', '밥 하다가·취사 중', '공사·보수작업 중',
    '체력단련 중', '기타'
  ],
  위험요인: \[
    '보호장비를 안 했다', '사전에 점검을 안 했다', '혼자 작업했다',
    '통제나 감독이 없었다', '장비가 낡거나 불량했다', '기타'
  ],
  환경요인: \[
    '밤이거나 어두웠다', '비나 눈이 왔다', '높은 곳이었다',
    '좁은 공간이었다', '경사지거나 미끄러웠다', '추웠거나 더웠다',
    '해당 없음', '기타'
  ],
  인적요인: \[
    '확인을 안 했다', '익숙하지 않은 작업이었다',
    '방심했거나 부주의했다', '안전수칙을 무시했다',
    '무리하게 작업했다', '해당 없음', '기타'
  ],
  사용장비: \[
    '차량·트럭', '총기류', '크레인·지게차', '조리기구',
    '전동공구·절단기', '해당 없음', '기타'
  ],
}

// 사용자 친화 라벨 → taxonomy 표준어 매핑 (LLM 보조용 힌트)
export const CHIP\_TAXONOMY\_MAP = {
  '몸이 끼었다': '끼임',
  '미끄러지거나 넘어졌다': '낙상',
  '높은 곳에서 떨어졌다': '추락',
  '차량 관련 사고': '교통',
  '불에 데거나 화재': '화재·화상',
  '날카로운 것에 베였다': '절단·베임',
  '물체에 부딪혔다': '충격',
  '보호장비를 안 했다': '보호장비미착용',
  '사전에 점검을 안 했다': '사전점검미흡',
  '혼자 작업했다': '단독작업',
  '통제나 감독이 없었다': '작업통제부족',
  '장비가 낡거나 불량했다': '장비노후화',
  '밤이거나 어두웠다': '야간',
  '비나 눈이 왔다': '우천',
  '높은 곳이었다': '고소작업',
  '좁은 공간이었다': '협소공간',
  '경사지거나 미끄러웠다': '미끄럼',
  '확인을 안 했다': '확인미흡',
  '익숙하지 않은 작업이었다': '숙련도부족',
  '방심했거나 부주의했다': '부주의',
  '안전수칙을 무시했다': '안전수칙미준수',
  '무리하게 작업했다': '무리한작업',
}
```

\---

## 관리자 화면 기능 목록

|기능|경로|설명|
|-|-|-|
|신규 검수|/admin/review|pending\_cases 목록, 승인·반려·수정|
|케이스 편집|/admin/cases|incident\_cases 전체 CRUD|
|taxonomy 관리|/admin/taxonomy|hazard/prevention 항목 추가·수정|
|데이터 내보내기|/admin/export|xlsx·CSV 다운로드|
|현황 대시보드|/admin/dashboard|차트: 유형별·부대별·월별|
|위험 트렌드|/admin/trends|증가 패턴 자동 감지|
|부대별 통계|/admin/units|부대 단위 비교|
|검수 대기 현황|/admin/queue|미승인 건수·처리 속도|
|사용자 관리|/admin/users|계정·권한|
|시스템 로그|/admin/logs|API 호출 이력|
|프롬프트 관리|/admin/prompts|LLM 시스템 프롬프트 수정·테스트|
|피드백 수집|/admin/feedback|예방대책 도움도 집계|

\---

## 실행 방법

```bash
# 1. 데이터 초기화 (xlsx → SQLite)
cd backend
uv run python scripts/init\_db.py

# 2. 백엔드 실행
uv run uvicorn main:app --reload --port 8000

# 3. 프론트엔드 실행
cd frontend
pnpm install
pnpm dev
```

\---

## 환경 변수 (.env)

```
ANTHROPIC\_API\_KEY=sk-ant-...
DATABASE\_URL=sqlite:///./accident.db
CORS\_ORIGINS=http://localhost:5173
```

\---

## codex 작업 지시

이 CLAUDE.md를 읽고 아래 순서로 개발해줘:

1. `backend/scripts/init\_db.py` — xlsx 3개 시트를 SQLite로 변환
2. `backend/models/schemas.py` — Pydantic 스키마 전체
3. `backend/services/llm\_engine.py` — LLM 정제 엔진
4. `backend/services/taxonomy.py` — taxonomy 매핑 로직
5. `backend/routers/analyze.py` — /api/normalize, /api/analyze
6. `backend/routers/cases.py` — 사례 조회 API
7. `backend/main.py` — FastAPI 앱 조립
8. `frontend/src/components/ChipSelector.tsx` — 칩 선택 컴포넌트
9. `frontend/src/components/STTButton.tsx` — 음성 입력 버튼
10. `frontend/src/components/AiBubble.tsx` — AI 추천 말풍선
11. `frontend/src/pages/InputFlow.tsx` — 10개 화면 전체 (검증 포함)
12. `frontend/src/pages/MyReports.tsx` — 내 신고 목록
13. `frontend/src/pages/ActionResult.tsx` — 조치결과 입력
14. `frontend/src/pages/admin/` — 관리자 화면들

각 파일 완성 후 `pnpm build` / `uv run pytest` 로 오류 확인.

