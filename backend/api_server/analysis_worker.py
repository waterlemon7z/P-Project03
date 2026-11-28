import asyncio
import logging
from pathlib import Path

import httpx
from pydantic import ValidationError

from config import Settings
from database import Store
from schemas import AIResult

logger = logging.getLogger(__name__)

RECOMMENDATIONS = {
    "high": "송금·앱 설치를 중단하고 해당 기관의 공식 연락처로 직접 확인하세요.",
    "medium": "개인정보 제공이나 링크 접속 전에 발신자를 공식 경로로 확인하세요.",
    "low": "분석 결과는 참고용이며, 금전·개인정보 요구는 별도로 확인하세요.",
    "unknown": "판단 근거가 부족합니다. 공식 기관에 직접 확인하세요.",
}


class AIClient:
    def __init__(
        self, settings: Settings, transport: httpx.BaseTransport | None = None
    ):
        self.settings = settings
        self.transport = transport

    def analyze(self, analysis_id: str, kind: str, payload: dict) -> dict:
        # Each job owns its HTTP client, including timeouts and file handles.
        with httpx.Client(
            base_url=self.settings.ai_base_url.rstrip("/") + "/",
            timeout=self.settings.ai_timeout_seconds,
            transport=self.transport,
        ) as client:
            if kind == "voice":
                path = Path(payload["path"])
                with path.open("rb") as audio:
                    response = client.post(
                        "internal/voice",
                        data={"id": analysis_id},
                        files={"file": (path.name, audio, payload["content_type"])},
                    )
            else:
                response = client.post(
                    f"internal/{kind}", json={"id": analysis_id, **payload}
                )
            response.raise_for_status()
            parsed = AIResult.model_validate(response.json())
            if str(parsed.id) != analysis_id:
                raise ValueError("AI response ID mismatch")
            return {
                **parsed.model_dump(mode="json", exclude={"id"}),
                "recommendation": RECOMMENDATIONS[parsed.risk_level],
            }


class AnalysisWorker:
    def __init__(self, store: Store, client: AIClient, settings: Settings):
        self.store, self.client, self.settings = store, client, settings
        self.stopping = asyncio.Event()

    def process_next(self) -> bool:
        # A crashed job becomes eligible again after its lease expires.
        job = self.store.claim(self.settings.ai_timeout_seconds * 5 + 60)
        if job is None:
            return False
        analysis_id, kind, payload, token = job
        result, error = None, None
        try:
            result = self.client.analyze(analysis_id, kind, payload)
        except httpx.TimeoutException:
            error = "AI 서버 응답 시간이 초과되었습니다."
        except httpx.HTTPStatusError:
            error = "AI 서버가 분석 요청을 처리하지 못했습니다."
        except httpx.RequestError:
            error = "AI 서버에 연결할 수 없습니다."
        except (ValidationError, ValueError):
            error = "AI 서버 응답 형식이 올바르지 않습니다."
        except Exception:
            logger.exception("Analysis failed: %s", analysis_id)
            error = "분석 처리 중 오류가 발생했습니다."
        if self.store.finish(analysis_id, token, result, error) and kind == "voice":
            try:
                Path(payload["path"]).unlink(missing_ok=True)
            except OSError:
                logger.exception("Upload cleanup failed: %s", analysis_id)
        return True

    async def run(self):
        while not self.stopping.is_set():
            try:
                if await asyncio.to_thread(self.process_next):
                    continue
            except Exception:
                logger.exception("Analysis worker iteration failed")
            try:
                await asyncio.wait_for(
                    self.stopping.wait(), timeout=self.settings.worker_poll_seconds
                )
            except TimeoutError:
                pass
