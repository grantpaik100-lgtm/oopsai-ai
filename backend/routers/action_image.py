import json
import os
import sqlite3
from base64 import b64decode
from typing import Any

from fastapi import APIRouter
from openai import OpenAI

from models.schemas import GeneratedImage, GenerateActionImageRequest, GenerateActionImageResponse
from services.ai_cache import get_cached_json, make_cache_key, set_cached_json
from services.db import get_connection

router = APIRouter(prefix="/api", tags=["action-image"])


def _json_dumps_model(value: object) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    return json.dumps(value, ensure_ascii=False, default=str)


def _load_step_status(value: str | None) -> dict[str, str]:
    default_status = {
        "backend1": "completed",
        "backend2": "completed",
        "backend3": "not_started",
    }
    if not value:
        return default_status

    try:
        loaded = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default_status

    if not isinstance(loaded, dict):
        return default_status

    merged = default_status.copy()
    for key in ("backend1", "backend2", "backend3"):
        existing = loaded.get(key)
        if isinstance(existing, str) and existing:
            merged[key] = existing
    return merged


def _backend3_step_status(existing_step_status: str | None, backend3_status: str) -> str:
    step_status = _load_step_status(existing_step_status)
    step_status["backend3"] = backend3_status
    return json.dumps(step_status, ensure_ascii=False)


def _build_mock_response(request: GenerateActionImageRequest) -> GenerateActionImageResponse:
    return GenerateActionImageResponse(
        case_id=request.case_id,
        images=[],
        safety_notice="이 이미지는 조치 후 예시이며 실제 현장 증빙이 아닙니다.",
        limitations=[
            "현재 시연버전에서는 실제 이미지 생성을 수행하지 않았거나 생성에 실패했습니다.",
            "실제 조치 완료 여부는 현장 확인 또는 실제 사진으로 검증해야 합니다.",
        ],
    )


def _strip_data_url(value: str) -> str:
    if "," in value and value.lstrip().startswith("data:"):
        return value.split(",", 1)[1]
    return value


def _build_image_prompt(request: GenerateActionImageRequest) -> str:
    return (
        "이 원본 현장 사진을 바탕으로 사용자가 확정한 안전 조치가 적용된 후의 "
        "참고용 예시 이미지를 생성한다. 실제 조치 완료 증빙사진이 아니며, 조치 "
        "가이드용이다. 원본 구도와 배경은 유지하고, 수정 대상 영역만 최소한으로 "
        "변경한다. 얼굴, 차량번호, 부대명, 민감 시설 표식은 흐리게 처리한다. "
        f"조치 내용: {request.selected_action.content}. "
        f"위험 맥락: {json.dumps(request.recommendation_context, ensure_ascii=False, default=str)}. "
        f"수정 대상: {request.image_edit_target.description}. "
        f"수정 방향: {request.image_edit_target.action_after_text or request.selected_action.content}."
    )


def _image_response_data(response: Any) -> list[Any]:
    data = getattr(response, "data", None)
    return data if isinstance(data, list) else []


def _try_generate_openai_image(request: GenerateActionImageRequest) -> GenerateActionImageResponse | None:
    if not os.getenv("OPENAI_API_KEY"):
        return None

    model = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1")
    cache_key = _action_image_cache_key(request, model)
    cached = get_cached_json("action_image", cache_key)
    if isinstance(cached, dict):
        try:
            return GenerateActionImageResponse.model_validate(cached)
        except Exception:
            pass

    prompt = _build_image_prompt(request)
    client = OpenAI(
        timeout=float(os.getenv("OPENAI_IMAGE_TIMEOUT_SECONDS", "12")),
        max_retries=int(os.getenv("OPENAI_MAX_RETRIES", "0")),
    )

    if request.source_image and request.source_image.base64_data:
        image_bytes = b64decode(_strip_data_url(request.source_image.base64_data))
        filename = request.source_image.filename or "source.png"
        mime_type = request.source_image.mime_type or "image/png"
        response = client.images.edit(
            model=model,
            image=(filename, image_bytes, mime_type),
            prompt=prompt,
            size="1024x1024",
            quality="low",
            n=1,
        )
    else:
        response = client.images.generate(
            model=model,
            prompt=prompt,
            size="1024x1024",
            quality="low",
            n=1,
        )

    images: list[GeneratedImage] = []
    for index, item in enumerate(_image_response_data(response)):
        b64_json = getattr(item, "b64_json", None)
        url = getattr(item, "url", None)
        if b64_json or url:
            images.append(
                GeneratedImage(
                    image_id=f"generated-{index + 1}",
                    url=url,
                    base64_data=b64_json,
                    mime_type="image/png",
                    prompt_summary="조치 가이드용 예시 이미지",
                )
            )

    if not images:
        return None

    result = GenerateActionImageResponse(
        case_id=request.case_id,
        images=images,
        safety_notice="이 이미지는 AI 생성 조치 가이드용 예시이며 실제 현장 증빙이 아닙니다.",
        limitations=[
            "원본 사진과 조치 내용을 바탕으로 생성한 참고 이미지입니다.",
            "실제 조치 완료 여부는 현장 확인 또는 실제 사진으로 검증해야 합니다.",
        ],
    )
    set_cached_json(
        "action_image",
        cache_key,
        model,
        request.model_dump(mode="json"),
        result.model_dump(mode="json"),
    )
    return result


def _action_image_cache_key(request: GenerateActionImageRequest, model: str) -> str:
    payload = request.model_dump(mode="json")
    source_image = payload.get("source_image")
    if isinstance(source_image, dict) and source_image.get("base64_data"):
        source_image["base64_data"] = make_cache_key("source_image", source_image["base64_data"])
    return make_cache_key("action_image", model, payload)


def _save_backend3_snapshot(
    request: GenerateActionImageRequest,
    response: GenerateActionImageResponse,
    backend3_status: str,
) -> None:
    if not request.case_id:
        return

    try:
        with get_connection() as connection:
            row = connection.execute(
                "SELECT step_status FROM pending_cases WHERE case_id = ?",
                (request.case_id,),
            ).fetchone()
            if row is None:
                print(f"Backend 3 snapshot skipped: case_id not found: {request.case_id}")
                return

            connection.execute(
                """
                UPDATE pending_cases
                SET backend3_input = ?,
                    backend3_output = ?,
                    step_status = ?
                WHERE case_id = ?
                """,
                (
                    _json_dumps_model(request),
                    _json_dumps_model(response),
                    _backend3_step_status(row["step_status"], backend3_status),
                    request.case_id,
                ),
            )
            connection.commit()
    except (FileNotFoundError, sqlite3.Error) as exc:
        _record_backend3_snapshot_error(request.case_id, exc)


def _record_backend3_snapshot_error(case_id: str, exc: Exception) -> None:
    try:
        with get_connection() as connection:
            connection.execute(
                """
                UPDATE pending_cases
                SET error_log = ?
                WHERE case_id = ?
                """,
                (f"Backend 3 snapshot failed: {exc}", case_id),
            )
            connection.commit()
    except Exception as log_exc:
        print(f"Backend 3 snapshot failed: {exc}; error_log update failed: {log_exc}")


@router.post("/generate-action-image", response_model=GenerateActionImageResponse)
def generate_action_image(
    request: GenerateActionImageRequest,
) -> GenerateActionImageResponse:
    backend3_status = "mock_completed"
    try:
        response = _try_generate_openai_image(request)
        if response is None:
            response = _build_mock_response(request)
        else:
            backend3_status = "completed"
    except Exception as exc:
        print(f"OpenAI image generation failed; using mock response: {exc}")
        response = _build_mock_response(request)

    _save_backend3_snapshot(request, response, backend3_status)
    return response
