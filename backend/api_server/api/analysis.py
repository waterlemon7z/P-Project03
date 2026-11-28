from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile

from schemas import (
    AcceptedAnalysis,
    AnalysisResult,
    AnalysisStatus,
    AnalysisType,
    ErrorResponse,
    HistoryResponse,
    SmsRequest,
    UrlRequest,
)

router = APIRouter(
    prefix="/api",
    tags=["analysis"],
    responses={
        422: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)


@router.post("/sms", response_model=AcceptedAnalysis, status_code=202)
def submit_sms(body: SmsRequest, request: Request):
    return AcceptedAnalysis(
        id=request.app.state.store.create("sms", {"text": body.text})
    )


@router.post("/url", response_model=AcceptedAnalysis, status_code=202)
def submit_url(body: UrlRequest, request: Request):
    return AcceptedAnalysis(
        id=request.app.state.store.create("url", {"url": str(body.url)})
    )


@router.post(
    "/voice",
    response_model=AcceptedAnalysis,
    status_code=202,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
    },
)
def submit_voice(request: Request, file: Annotated[UploadFile, File()]):
    settings = request.app.state.settings
    extension = Path(file.filename or "").suffix.lower()
    content_types = {".wav": "audio/wav", ".mp3": "audio/mpeg", ".m4a": "audio/mp4"}
    path = None
    try:
        if extension not in content_types:
            raise HTTPException(415, "WAV, MP3, M4A 파일만 업로드할 수 있습니다.")
        analysis_id = str(uuid4())
        path = settings.upload_dir / f"{analysis_id}{extension}"
        size = 0
        with path.open("xb") as destination:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    raise HTTPException(
                        413, "음성 파일이 업로드 용량 제한을 초과했습니다."
                    )
                destination.write(chunk)
        if size == 0:
            raise HTTPException(400, "빈 음성 파일은 분석할 수 없습니다.")
        request.app.state.store.create(
            "voice",
            {"path": str(path), "content_type": content_types[extension]},
            analysis_id,
        )
        return AcceptedAnalysis(id=analysis_id)
    except Exception:
        if path is not None:
            path.unlink(missing_ok=True)
        raise
    finally:
        file.file.close()


@router.get(
    "/result/{id}",
    response_model=AnalysisResult,
    responses={404: {"model": ErrorResponse}},
)
def get_result(id: UUID, request: Request):
    result = request.app.state.store.get(str(id))
    if result is None:
        raise HTTPException(404, "분석 결과를 찾을 수 없습니다.")
    return result


@router.get("/history", response_model=HistoryResponse)
def get_history(
    request: Request,
    type: AnalysisType | None = None,
    status: AnalysisStatus | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
):
    return request.app.state.store.history(type, status, limit, offset)
