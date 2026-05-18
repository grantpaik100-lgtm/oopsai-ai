# API 명세서

> Base URL: `https://api.example.com/v1`
> 인증: `Authorization: Bearer <JWT>` (로그인/회원가입 제외 전체 필수)
> 응답 형식: `Content-Type: application/json`

---

## 공통 응답 구조

```json
// 성공
{ "success": true, "data": { ... } }

// 실패
{ "success": false, "error": { "code": "ERROR_CODE", "message": "설명" } }
```

### 공통 에러 코드

| 코드 | HTTP | 설명 |
|------|------|------|
| `UNAUTHORIZED` | 401 | 토큰 없음 또는 만료 |
| `FORBIDDEN` | 403 | 권한 없음 |
| `NOT_FOUND` | 404 | 리소스 없음 |
| `VALIDATION_ERROR` | 422 | 요청 파라미터 오류 |
| `INTERNAL_ERROR` | 500 | 서버 오류 |

---

## 1. 인증 (Auth)

### POST /auth/login — 로그인

**권한:** 없음

**Request Body**
```json
{
  "username": "hong123",
  "password": "plain_password",
  "fcm_token": "fcm_device_token_string"
}
```

**Response 200**
```json
{
  "success": true,
  "data": {
    "access_token": "eyJhbGci...",
    "token_type": "bearer",
    "user": {
      "id": 1,
      "name": "홍길동",
      "rank": "대위",
      "role": "officer",
      "approval_status": "approved",
      "unit": { "id": 10, "name": "1중대" }
    }
  }
}
```

**에러**
| 코드 | 상황 |
|------|------|
| `INVALID_CREDENTIALS` | 아이디/비밀번호 불일치 |
| `ACCOUNT_PENDING` | 승인 대기 중 |
| `ACCOUNT_REJECTED` | 계정 거절됨 |

---

### POST /auth/register — 회원가입 신청

**권한:** 없음

**Request Body**
```json
{
  "username": "hong123",
  "password": "plain_password",
  "name": "홍길동",
  "rank": "대위",
  "military_id": "24-1234567",
  "unit_id": 10
}
```

**Response 201**
```json
{
  "success": true,
  "data": { "id": 42, "approval_status": "pending" }
}
```

**에러**
| 코드 | 상황 |
|------|------|
| `DUPLICATE_USERNAME` | 이미 존재하는 아이디 |
| `DUPLICATE_MILITARY_ID` | 이미 등록된 군번 |

---

### POST /auth/logout — 로그아웃

**권한:** 전체 (승인된 계정)

FCM 토큰을 DB에서 삭제합니다.

**Response 200**
```json
{ "success": true, "data": null }
```

---

### GET /auth/me — 내 프로필 조회

**권한:** 전체

**Response 200**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "username": "hong123",
    "name": "홍길동",
    "rank": "대위",
    "military_id": "24-1234567",
    "role": "officer",
    "approval_status": "approved",
    "unit": { "id": 10, "name": "1중대", "parent": { "id": 5, "name": "1대대" } }
  }
}
```

---

## 2. 사용자 (Users)

### PUT /users/me — 내 정보 수정

**권한:** 전체

**Request Body** (변경할 항목만 포함)
```json
{
  "name": "홍길동",
  "rank": "소령",
  "current_password": "old_pw",
  "new_password": "new_pw"
}
```

**Response 200**
```json
{ "success": true, "data": { "id": 1, "name": "홍길동", "rank": "소령" } }
```

---

### GET /users — 사용자 목록

**권한:** admin, system_admin

**Query Parameters**
| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `approval_status` | string | `pending` / `approved` / `rejected` |
| `role` | string | `officer` / `admin` / `commander` |
| `unit_id` | integer | 소속 부대 필터 |
| `page` | integer | 페이지 번호 (기본 1) |
| `size` | integer | 페이지 크기 (기본 20) |

**Response 200**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": 42,
        "name": "김철수",
        "rank": "중사",
        "military_id": "20-9876543",
        "role": "officer",
        "approval_status": "pending",
        "unit": { "id": 10, "name": "1중대" },
        "created_at": "2026-05-16T09:00:00Z"
      }
    ],
    "total": 38,
    "page": 1,
    "size": 20
  }
}
```

---

### PUT /users/{id}/approve — 계정 승인

**권한:** admin (자기 부대 계층 내), system_admin

**Response 200**
```json
{ "success": true, "data": { "id": 42, "approval_status": "approved" } }
```

---

### PUT /users/{id}/reject — 계정 거절

**권한:** admin, system_admin

**Request Body**
```json
{ "rejection_reason": "군번 불일치" }
```

**Response 200**
```json
{ "success": true, "data": { "id": 42, "approval_status": "rejected" } }
```

---

### POST /admin/users — 관리자 계정 생성

**권한:** system_admin

**Request Body**
```json
{
  "username": "admin01",
  "password": "init_pw",
  "name": "이관리",
  "rank": "원사",
  "military_id": "18-1112222",
  "unit_id": 5,
  "role": "admin"
}
```

**Response 201**
```json
{ "success": true, "data": { "id": 99, "role": "admin", "approval_status": "approved" } }
```

---

### PUT /admin/users/{id} — 관리자 계정 수정

**권한:** system_admin

**Request Body** (변경할 항목만)
```json
{ "name": "이관리", "unit_id": 7, "role": "commander" }
```

**Response 200**
```json
{ "success": true, "data": { "id": 99, "name": "이관리", "role": "commander" } }
```

---

### DELETE /admin/users/{id} — 관리자 계정 삭제

**권한:** system_admin

**Response 200**
```json
{ "success": true, "data": null }
```

---

## 3. 부대 (Units)

### GET /units — 부대 목록 (트리)

**권한:** 전체

**Query Parameters**
| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `flat` | boolean | true 시 트리 대신 평탄화 목록 반환 |

**Response 200**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "name": "1사단",
      "level": "division",
      "children": [
        {
          "id": 3,
          "name": "1연대",
          "level": "regiment",
          "children": [ ... ]
        }
      ]
    }
  ]
}
```

---

## 4. 아차사고 (Accidents)

### POST /accidents — 사고 등록

**권한:** officer, admin

등록 완료 시 임베딩을 비동기로 생성하여 `embedding` 컬럼에 저장합니다.

**Request Body**
```json
{
  "occurred_at": "2026-05-16T08:30:00Z",
  "location": "훈련장 A구역",
  "description": "탄약 운반 중 발이 미끄러져 넘어질 뻔함",
  "accident_type": "안전사고",
  "risk_level": "high",
  "ai_recommended": true,
  "action_mode": "later",
  "action_description": null,
  "photo_keys": ["accidents/uuid1.jpg", "accidents/uuid2.jpg"]
}
```

> `action_mode`: `"now"` (즉시 조치) | `"later"` (나중에)
> `action_mode = "later"` 이면 `is_public = false`, `action_status = "pending"`

**Response 201**
```json
{
  "success": true,
  "data": {
    "id": 201,
    "is_public": false,
    "action_status": "pending",
    "review_status": "normal"
  }
}
```

---

### GET /accidents — 사고 목록

**권한:** officer(자기 부대), admin(담당 부대), commander(예하 전체), system_admin(전체)

**Query Parameters**
| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `unit_id` | integer | 부대 필터 (하위 부대 포함) |
| `accident_type` | string | 사고 유형 필터 |
| `risk_level` | string | `low` / `medium` / `high` |
| `action_status` | string | `pending` / `completed` |
| `review_status` | string | `normal` / `rejected` |
| `from` | date | 발생일 시작 (YYYY-MM-DD) |
| `to` | date | 발생일 종료 |
| `page` | integer | 기본 1 |
| `size` | integer | 기본 20 |

**Response 200**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": 201,
        "occurred_at": "2026-05-16T08:30:00Z",
        "location": "훈련장 A구역",
        "accident_type": "안전사고",
        "risk_level": "high",
        "action_status": "pending",
        "review_status": "normal",
        "is_public": false,
        "reporter": { "id": 1, "name": "홍길동", "rank": "대위" },
        "unit": { "id": 10, "name": "1중대" },
        "thumbnail_url": "https://storage.example.com/accidents/uuid1.jpg"
      }
    ],
    "total": 54,
    "page": 1,
    "size": 20
  }
}
```

---

### GET /accidents/my — 내 사고 목록

**권한:** officer, admin

`GET /accidents` 에서 `reporter_id = 내 ID` 로 필터한 결과와 동일하나, 비공개 포함 전체 반환합니다.

**Query Parameters:** `action_status`, `page`, `size`

**Response 200:** `GET /accidents` 동일 구조

---

### GET /accidents/{id} — 사고 상세

**권한:** officer(자기 사고 또는 공개), admin(담당 부대), commander, system_admin

**Response 200**
```json
{
  "success": true,
  "data": {
    "id": 201,
    "occurred_at": "2026-05-16T08:30:00Z",
    "location": "훈련장 A구역",
    "description": "탄약 운반 중 발이 미끄러져 넘어질 뻔함",
    "accident_type": "안전사고",
    "risk_level": "high",
    "ai_recommended": true,
    "action_status": "pending",
    "action_mode": "later",
    "action_description": null,
    "action_completed_at": null,
    "is_public": false,
    "review_status": "normal",
    "rejection_reason": null,
    "reporter": { "id": 1, "name": "홍길동", "rank": "대위" },
    "unit": { "id": 10, "name": "1중대" },
    "photos": [
      { "id": 1, "photo_type": "scene", "url": "https://...", "order_index": 0 }
    ],
    "prevention_cards": [
      { "id": 1, "card_text": "작업 전 지면 상태 확인", "image_url": "https://...", "order_index": 0 }
    ],
    "created_at": "2026-05-16T09:00:00Z",
    "updated_at": "2026-05-16T09:00:00Z"
  }
}
```

---

### PUT /accidents/{id} — 사고 수정

**권한:** officer(자기 사고), admin (수정 불가 — review_status 변경만 가능)

수정 시 변경된 필드 전체를 `accident_history` 에 기록합니다.

**Request Body** (변경할 항목만)
```json
{
  "description": "수정된 상황 설명",
  "accident_type": "부주의",
  "risk_level": "medium",
  "action_description": "미끄럼 방지 매트 설치 완료"
}
```

**Response 200**
```json
{ "success": true, "data": { "id": 201, "updated_at": "2026-05-16T10:00:00Z" } }
```

---

### PUT /accidents/{id}/review — 관리자 검토 (승인/반려)

**권한:** admin

**Request Body**
```json
{
  "review_status": "rejected",
  "rejection_reason": "사고 유형 분류 오류"
}
```

> `review_status = "rejected"` 이면 `is_public = false` 로 전환, 담당자에게 FCM 푸시 발송

**Response 200**
```json
{ "success": true, "data": { "id": 201, "review_status": "rejected", "is_public": false } }
```

---

### POST /accidents/{id}/complete — 조치 완료 인증

**권한:** officer(자기 사고)

조치 사진 등록 후 `action_status = "completed"`, `is_public = true` 로 전환합니다.

**Request Body**
```json
{
  "action_description": "미끄럼 방지 매트 설치",
  "action_photo_keys": ["accidents/action_uuid.jpg"]
}
```

**Response 200**
```json
{
  "success": true,
  "data": {
    "id": 201,
    "action_status": "completed",
    "action_completed_at": "2026-05-16T11:00:00Z",
    "is_public": true
  }
}
```

---

### GET /accidents/{id}/history — 수정 이력

**권한:** officer(자기 사고), admin, commander, system_admin

**Response 200**
```json
{
  "success": true,
  "data": [
    {
      "id": 1,
      "field_name": "description",
      "old_value": "원래 내용",
      "new_value": "수정된 내용",
      "changed_by": { "id": 1, "name": "홍길동", "rank": "대위" },
      "changed_at": "2026-05-16T10:00:00Z"
    }
  ]
}
```

---

## 5. 사진 (Photos)

### GET /accidents/photos/upload-url — S3 Presigned URL 발급

**권한:** officer, admin

클라이언트가 서버를 거치지 않고 직접 S3에 업로드할 수 있도록 Presigned URL을 발급합니다.

**Query Parameters**
| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `filename` | string | 원본 파일명 (확장자 포함) |
| `photo_type` | string | `scene` (현장) / `action` (조치) |

**Response 200**
```json
{
  "success": true,
  "data": {
    "upload_url": "https://storage.googleapis.com/bucket/accidents/uuid.jpg?X-Goog-Signature=...",
    "file_key": "accidents/uuid.jpg",
    "expires_in": 300
  }
}
```

---

### DELETE /accidents/{id}/photos/{photoId} — 사진 삭제

**권한:** officer(자기 사고)

**Response 200**
```json
{ "success": true, "data": null }
```

---

## 6. AI 분석

### POST /ai/analyze — 사진+텍스트 분석

**권한:** officer, admin

REG-01 제출 후 호출. GPT-4o Vision으로 사고 유형·위험도 추천 및 추가 질문을 생성합니다.

**Request Body**
```json
{
  "description": "탄약 운반 중 발이 미끄러져 넘어질 뻔함",
  "photo_keys": ["accidents/uuid1.jpg"]
}
```

**Response 200**
```json
{
  "success": true,
  "data": {
    "suggested_type": "안전사고",
    "suggested_risk_level": "high",
    "follow_up_questions": [
      "미끄러진 정확한 위치가 어디인가요?",
      "당시 날씨나 지면 상태는 어떠했나요?",
      "탄약 무게나 운반 방법에 대해 추가로 설명해주세요."
    ]
  }
}
```

---

### POST /ai/prevention — 예방 대책 카드 생성

**권한:** officer, admin

REG-04 완료 후 호출. GPT-4o로 대책 텍스트 생성 + DALL·E 3으로 이미지 3장 생성.
생성 결과는 `prevention_cards` 테이블에 저장 후 반환합니다.

**Request Body**
```json
{
  "accident_id": 201,
  "accident_type": "안전사고",
  "risk_level": "high",
  "description": "탄약 운반 중 발이 미끄러져 넘어질 뻔함"
}
```

**Response 200**
```json
{
  "success": true,
  "data": {
    "cards": [
      {
        "id": 1,
        "card_text": "작업 전 지면 상태(습기·장애물) 확인 필수",
        "image_url": "https://storage.example.com/prevention/img1.png",
        "order_index": 0
      },
      {
        "id": 2,
        "card_text": "2인 1조 운반 원칙 준수",
        "image_url": "https://storage.example.com/prevention/img2.png",
        "order_index": 1
      },
      {
        "id": 3,
        "card_text": "미끄럼 방지 장갑·안전화 착용 확인",
        "image_url": "https://storage.example.com/prevention/img3.png",
        "order_index": 2
      }
    ]
  }
}
```

---

### POST /ai/similar — 유사 사례 검색

**권한:** officer, admin, commander

pgvector 코사인 유사도로 가장 유사한 공개 사례를 반환합니다.

**Request Body**
```json
{
  "description": "탄약 운반 중 발이 미끄러져 넘어질 뻔함",
  "limit": 5
}
```

**Response 200**
```json
{
  "success": true,
  "data": [
    {
      "id": 88,
      "occurred_at": "2025-11-03",
      "location": "탄약고 인근",
      "accident_type": "안전사고",
      "risk_level": "high",
      "description": "탄약 이동 중 경사면에서 미끄러짐",
      "similarity": 0.94,
      "unit": { "id": 8, "name": "3중대" }
    }
  ]
}
```

---

## 7. 통계 (Statistics)

### GET /statistics/monthly — 월별/유형별 현황

**권한:** officer, admin, commander

**Query Parameters**
| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `unit_id` | integer | 기준 부대 (예하 전체 포함) |
| `year` | integer | 조회 연도 (기본: 현재 연도) |

**Response 200**
```json
{
  "success": true,
  "data": {
    "monthly": [
      { "month": "2026-01", "total": 5, "by_type": { "안전사고": 3, "부주의": 2 } },
      { "month": "2026-02", "total": 8, "by_type": { "안전사고": 5, "장비": 3 } }
    ],
    "total_year": 54
  }
}
```

---

### GET /statistics/units — 예하부대 등록 현황

**권한:** admin, commander

**Query Parameters**
| 파라미터 | 타입 | 설명 |
|---------|------|------|
| `unit_id` | integer | 기준 부대 |
| `from` | date | 기간 시작 |
| `to` | date | 기간 종료 |

**Response 200**
```json
{
  "success": true,
  "data": [
    { "unit": { "id": 10, "name": "1중대" }, "total": 12, "pending": 3, "completed": 9 },
    { "unit": { "id": 11, "name": "2중대" }, "total": 7, "pending": 1, "completed": 6 }
  ]
}
```

---

## 8. 보고서 (Reports)

### GET /reports — 보고서 목록

**권한:** admin, commander

**Query Parameters:** `page`, `size`

**Response 200**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": 5,
        "title": "2026년 4월 월간 안전 보고서",
        "period": "2026-04",
        "created_at": "2026-05-01T09:00:00Z"
      }
    ],
    "total": 5
  }
}
```

---

### POST /reports/generate — 보고서 생성

**권한:** admin, commander

**Request Body**
```json
{
  "period_type": "monthly",
  "year": 2026,
  "month": 4,
  "unit_id": 5
}
```

**Response 201**
```json
{
  "success": true,
  "data": { "id": 6, "title": "2026년 4월 월간 안전 보고서" }
}
```

---

### GET /reports/{id}/download-url — 보고서 다운로드 URL

**권한:** admin, commander

**Response 200**
```json
{
  "success": true,
  "data": {
    "download_url": "https://storage.example.com/reports/report_6.pdf?...",
    "expires_in": 300
  }
}
```

---

## 9. 공지사항 (Notices)

### GET /notices — 공지사항 목록

**권한:** 전체

**Query Parameters:** `page`, `size`

**Response 200**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": 10,
        "title": "하계 안전 교육 공지",
        "is_important": true,
        "author": { "id": 2, "name": "이관리", "rank": "원사" },
        "created_at": "2026-05-10T09:00:00Z"
      }
    ],
    "total": 23
  }
}
```

---

### GET /notices/{id} — 공지사항 상세

**권한:** 전체

**Response 200**
```json
{
  "success": true,
  "data": {
    "id": 10,
    "title": "하계 안전 교육 공지",
    "content": "다음과 같이 안전 교육을 실시합니다...",
    "is_important": true,
    "author": { "id": 2, "name": "이관리", "rank": "원사" },
    "attachments": [
      { "id": 1, "file_name": "교육계획서.pdf", "file_key": "notices/file1.pdf" }
    ],
    "created_at": "2026-05-10T09:00:00Z",
    "updated_at": "2026-05-10T09:00:00Z"
  }
}
```

---

### POST /notices — 공지사항 작성

**권한:** admin, system_admin

**Request Body**
```json
{
  "title": "하계 안전 교육 공지",
  "content": "다음과 같이 안전 교육을 실시합니다...",
  "is_important": true,
  "attachment_keys": ["notices/file1.pdf"]
}
```

**Response 201**
```json
{ "success": true, "data": { "id": 10 } }
```

---

### PUT /notices/{id} — 공지사항 수정

**권한:** admin(작성자), system_admin

**Request Body** (변경할 항목만)
```json
{ "title": "수정된 제목", "is_important": false }
```

**Response 200**
```json
{ "success": true, "data": { "id": 10, "updated_at": "2026-05-16T12:00:00Z" } }
```

---

### DELETE /notices/{id} — 공지사항 삭제

**권한:** admin(작성자), system_admin

**Response 200**
```json
{ "success": true, "data": null }
```

---

### GET /notices/{id}/attachments/{fileId}/download-url — 첨부파일 다운로드 URL

**권한:** 전체

**Response 200**
```json
{
  "success": true,
  "data": { "download_url": "https://...", "expires_in": 300 }
}
```

---

## 10. 알림 (Notifications)

### GET /notifications — 알림 목록

**권한:** 전체

**Query Parameters:** `page`, `size`, `is_read` (boolean)

**Response 200**
```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": 55,
        "type": "overdue_action",
        "title": "조치 기한 초과",
        "body": "등록하신 사고의 조치 기한이 초과되었습니다.",
        "related_id": 201,
        "related_type": "accident",
        "is_read": false,
        "sent_at": "2026-05-16T08:00:00Z"
      }
    ],
    "total": 12,
    "unread_count": 3
  }
}
```

**알림 type 목록**

| type | 발생 시점 |
|------|---------|
| `overdue_action` | 조치 기한 초과 |
| `signup_approval` | 회원가입 승인/거절 결과 |
| `action_prompt` | 조치 독촉 (관리자 → 간부) |
| `rejection_alert` | 사고 반려 알림 |
| `notice_alert` | 새 공지사항 등록 |

---

### PUT /notifications/{id}/read — 알림 읽음 처리

**권한:** 전체 (본인 알림만)

**Response 200**
```json
{ "success": true, "data": { "id": 55, "is_read": true } }
```

---

### PUT /notifications/read-all — 전체 알림 읽음 처리

**권한:** 전체

**Response 200**
```json
{ "success": true, "data": { "updated_count": 3 } }
```

---

### GET /notifications/settings — 알림 설정 조회

**권한:** 전체

**Response 200**
```json
{
  "success": true,
  "data": {
    "all_enabled": true,
    "overdue_action": true,
    "signup_approval": true,
    "action_prompt": true,
    "rejection_alert": true,
    "notice_alert": false
  }
}
```

---

### PUT /notifications/settings — 알림 설정 수정

**권한:** 전체

**Request Body** (변경할 항목만)
```json
{ "notice_alert": true, "all_enabled": true }
```

**Response 200**
```json
{ "success": true, "data": { "all_enabled": true, "notice_alert": true } }
```

---

## 11. API 엔드포인트 요약

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| POST | `/auth/login` | 로그인 | 없음 |
| POST | `/auth/register` | 회원가입 신청 | 없음 |
| POST | `/auth/logout` | 로그아웃 | 전체 |
| GET | `/auth/me` | 내 프로필 | 전체 |
| PUT | `/users/me` | 내 정보 수정 | 전체 |
| GET | `/users` | 사용자 목록 | admin+ |
| PUT | `/users/{id}/approve` | 계정 승인 | admin+ |
| PUT | `/users/{id}/reject` | 계정 거절 | admin+ |
| POST | `/admin/users` | 관리자 계정 생성 | system_admin |
| PUT | `/admin/users/{id}` | 관리자 계정 수정 | system_admin |
| DELETE | `/admin/users/{id}` | 관리자 계정 삭제 | system_admin |
| GET | `/units` | 부대 목록 | 전체 |
| POST | `/accidents` | 사고 등록 | officer, admin |
| GET | `/accidents` | 사고 목록 | 권한별 범위 |
| GET | `/accidents/my` | 내 사고 목록 | officer, admin |
| GET | `/accidents/{id}` | 사고 상세 | 권한별 |
| PUT | `/accidents/{id}` | 사고 수정 | officer(본인) |
| PUT | `/accidents/{id}/review` | 관리자 검토 | admin |
| POST | `/accidents/{id}/complete` | 조치 완료 | officer(본인) |
| GET | `/accidents/{id}/history` | 수정 이력 | officer+ |
| GET | `/accidents/photos/upload-url` | 사진 업로드 URL | officer, admin |
| DELETE | `/accidents/{id}/photos/{photoId}` | 사진 삭제 | officer(본인) |
| POST | `/ai/analyze` | 사진+텍스트 분석 | officer, admin |
| POST | `/ai/prevention` | 예방 대책 생성 | officer, admin |
| POST | `/ai/similar` | 유사 사례 검색 | officer+ |
| GET | `/statistics/monthly` | 월별/유형별 통계 | officer+ |
| GET | `/statistics/units` | 예하부대 현황 | admin+ |
| GET | `/reports` | 보고서 목록 | admin+ |
| POST | `/reports/generate` | 보고서 생성 | admin+ |
| GET | `/reports/{id}/download-url` | 보고서 다운로드 | admin+ |
| GET | `/notices` | 공지사항 목록 | 전체 |
| GET | `/notices/{id}` | 공지사항 상세 | 전체 |
| POST | `/notices` | 공지사항 작성 | admin+ |
| PUT | `/notices/{id}` | 공지사항 수정 | admin+(작성자) |
| DELETE | `/notices/{id}` | 공지사항 삭제 | admin+(작성자) |
| GET | `/notices/{id}/attachments/{fileId}/download-url` | 첨부 다운로드 | 전체 |
| GET | `/notifications` | 알림 목록 | 전체 |
| PUT | `/notifications/{id}/read` | 알림 읽음 | 전체(본인) |
| PUT | `/notifications/read-all` | 전체 읽음 | 전체 |
| GET | `/notifications/settings` | 알림 설정 조회 | 전체 |
| PUT | `/notifications/settings` | 알림 설정 수정 | 전체 |
