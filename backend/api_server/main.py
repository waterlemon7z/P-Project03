import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from analysis_worker import AIClient, AnalysisWorker
from api.analysis import router as analysis_router
from api.health import router as health_router
from config import Settings
from database import Store


def create_app(
    settings: Settings | None = None,
    ai_client: AIClient | None = None,
    *,
    start_worker: bool = True,
) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        store = Store(settings.database_url)
        try:
            store.initialize()
            settings.upload_dir.mkdir(parents=True, exist_ok=True)
            app.state.store = store
            worker = AnalysisWorker(store, ai_client or AIClient(settings), settings)
            app.state.worker = worker
            task = asyncio.create_task(worker.run()) if start_worker else None
            try:
                yield
            finally:
                worker.stopping.set()
                if task:
                    await task
        finally:
            store.engine.dispose()

    app = FastAPI(
        title="보이스피싱 감지 API",
        description="Android 앱과 AI 분석 서버를 연결하는 REST API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.settings = settings

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        return JSONResponse(
            {"error": str(exc.detail)}, status_code=exc.status_code, headers=exc.headers
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        message = "; ".join(
            f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()
        )
        return JSONResponse({"error": message}, status_code=422)

    @app.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception):
        logging.getLogger(__name__).exception("Unhandled API error")
        return JSONResponse(
            {"error": "서버 처리 중 오류가 발생했습니다."}, status_code=500
        )

    app.include_router(health_router)
    app.include_router(analysis_router)
    return app


app = create_app()
