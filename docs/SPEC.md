# PROJECT_SPEC.md

## 1. 프로젝트 구조

```text
P-Project03/
├── frontend/          # Android 앱
├── backend/
│   ├── api_server/    # FastAPI REST API 서버 (독립 프로젝트)
│   └── services/      # AI 모델·추론 코드
├── llm/               # AI 분석 서버
│   ├── voice/         # 보이스피싱 분석
│   ├── sms/           # 스미싱 분석
│   └── url/           # 피싱 URL 분석
├── data/
└── docs/
```

## 2. 시스템 구조

```text
Frontend (Android)
       ↕ REST API
Backend (FastAPI) ↔ PostgreSQL
       ↕ Internal REST API
LLM / AI Server
       ├── Voice
       ├── SMS
       └── URL
```

## 3. Frontend ↔ Backend

### API 목록

| Method | Endpoint | 용도 |
|---|---|---|
| GET | /health | 서버 상태 확인 |
| POST | /api/voice | 녹음 파일 분석 |
| POST | /api/sms | 문자 분석 |
| POST | /api/url | URL 분석 |
| GET | /api/result/{id} | 분석 결과 조회 |
| GET | /api/history | 분석 이력 조회 |

### 요청 데이터

| 분석 유형 | 필드 | 타입 | 형식 |
|---|---|---|---|
| Voice | file | File | Multipart (WAV, MP3, M4A) |
| SMS | text | string | JSON |
| URL | url | string | JSON |

### 분석 요청 응답

HTTP `202 Accepted`. 작업을 DB에 저장한 뒤 반환하고 백그라운드 워커가 AI 서버를 호출합니다.

```json
{
  "id": "uuid",
  "status": "pending"
}
```

### 분석 결과 응답

```json
{
  "id": "uuid",
  "type": "voice",
  "status": "completed",
  "risk_level": "high",
  "summary": "보이스피싱 의심",
  "reasons": ["기관 사칭", "송금 요구"],
  "recommendation": "공식 기관에 직접 확인하세요."
}
```

| 필드 | 타입 |
|---|---|
| id | string (UUID) |
| type | enum (voice, sms, url) |
| status | enum |
| risk_level | enum 또는 null |
| summary | string 또는 null |
| reasons | string[] |
| recommendation | string 또는 null |
| error | string 또는 null (선택) |

구현 응답에는 `score`(0.0~1.0 또는 null), `details`(object),
`created_at`/`updated_at`(UTC ISO 8601)도 포함합니다.
결과가 아직 없으면 분석 필드는 null 또는 빈 목록·객체입니다.
존재하지 않는 UUID는 HTTP 404, UUID 형식 오류는 HTTP 422입니다.

### 이력 조회

`GET /api/history`는 최신 생성순이며 생성 시각이 같으면 UUID 내림차순으로 정렬합니다.

| Query | 기본값 | 조건 |
|---|---|---|
| type | 없음 | voice, sms, url |
| status | 없음 | pending, processing, completed, failed |
| limit | 20 | 1~100 |
| offset | 0 | 0 이상 |

응답: `{"items":[분석 결과 객체],"total":42,"limit":20,"offset":0}`.
`total`은 필터 적용 후 페이지네이션 전 건수입니다.
현재는 인증·사용자별 이력 구분이 없습니다.

### 입력 검증

- SMS: 양끝 공백 제거 후 1~10,000자.
- URL: HTTP(S) URL, 최대 8,192자.
- Voice: WAV/MP3/M4A 확장자, 빈 파일 불가, 기본 최대 20 MiB(설정 가능).
- 잘못된 요청은 HTTP 422, 빈 음성 파일은 400, 파일 크기 초과는 413, 미지원 확장자는 415.
- AI 연결·응답 실패는 접수 후 작업 상태 `failed`와 `error`로 조회합니다.

## 4. Backend ↔ LLM

### API 목록

| Method | Endpoint |
|---|---|
| GET | /health |
| POST | /internal/voice |
| POST | /internal/sms |
| POST | /internal/url |

### 요청 데이터

| 모듈 | 필드 | 타입 | 형식 |
|---|---|---|---|
| Voice | id, file | string, File | Multipart |
| SMS | id, text | string, string | JSON |
| URL | id, url | string, string | JSON |

### 공통 응답 데이터

```json
{
  "id": "uuid",
  "risk_level": "high",
  "score": 0.92,
  "summary": "금융사기 의심",
  "reasons": ["위험 판단 근거"],
  "details": {}
}
```

| 필드 | 타입 |
|---|---|
| id | string (UUID) |
| risk_level | enum |
| score | float (0.0~1.0) 또는 null |
| summary | string |
| reasons | string[] |
| details | object |

### Voice 전용 details

```json
{
  "transcript": "전체 STT 텍스트",
  "segments": [
    {
      "start": 0.0,
      "end": 3.5,
      "text": "발화 내용"
    }
  ]
}
```

### SMS 전용 details

```json
{
  "urls": ["https://example.com"],
  "suspicious_texts": ["의심 문구"]
}
```

### URL 전용 details

```json
{
  "domain": "example.com",
  "blacklisted": null,
  "suspicious_features": ["의심 특징"]
}
```

## 5. 공통 Enum

### status

- pending
- processing
- completed
- failed

### risk_level

- low
- medium
- high
- unknown

## 6. 오류 응답

HTTP 4xx 또는 5xx:

```json
{
  "error": "분석 실패 원인"
}
```

## 7. 통신 방식

| 구간 | 방식 |
|---|---|
| Frontend ↔ Backend | REST API |
| Backend ↔ LLM | Internal REST API |
| Frontend ↔ LLM | 직접 통신하지 않음 |

- 구조화된 데이터: UTF-8 JSON
- 음성 파일: multipart/form-data
- 시간 단위: 초(float)
- 분석 결과 조회: REST Polling
- 실시간 음성 분석 및 WebSocket 미사용
