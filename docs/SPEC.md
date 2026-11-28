# PROJECT_SPEC.md

## 1. 프로젝트 구조

```text
P-Project03/
├── frontend/          # Android 앱
├── backend/           # FastAPI 서버
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