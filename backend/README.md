# Backend

서로 다른 역할의 프로젝트를 하위 디렉터리로 구분합니다.

```text
backend/
├── api_server/  # FastAPI REST API 서버, 독립 의존성·설정·테스트
└── services/    # AI 모델·추론 코드
    └── url/
```

REST API의 실행 방법과 설정은 [api_server/README.md](api_server/README.md)를 참고하세요.
프로젝트 루트에서 실행합니다.

```bash
source .venv/bin/activate
uv sync --active --inexact --project backend/api_server --locked
uv run --active --inexact --directory backend/api_server uvicorn main:app --reload
```
