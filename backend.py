import os
import io
import json
import base64
import hashlib
import secrets
import string
import time
from dataclasses import dataclass
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv
from PIL import Image

load_dotenv()


# ──────────────────────────────────────────────────────────────
# 图片工具
# ──────────────────────────────────────────────────────────────

def image_bytes_to_image(image_bytes: bytes) -> Image.Image:
    """将图片二进制数据转换为 RGB PIL Image。"""
    return Image.open(io.BytesIO(image_bytes)).convert("RGB")


def base64_to_image(data_url: str) -> Image.Image:
    """将剪贴板组件返回的 base64 data URL 转换为 PIL Image。"""
    _, data = data_url.split(",", 1)
    return image_bytes_to_image(base64.b64decode(data))


# ──────────────────────────────────────────────────────────────
# 使用次数统计
# ──────────────────────────────────────────────────────────────
_STATS_FILE = Path(__file__).parent / "usage_stats.json"


def _read_usage_stats() -> dict:
    stats = {"total": 0, "models": {}}
    try:
        if _STATS_FILE.exists():
            with open(_STATS_FILE, "r", encoding="utf-8") as f:
                stats.update(json.load(f))
        stats["models"] = stats.get("models") or {}
    except Exception:
        pass
    return stats


def increment_usage(model: str, elapsed: float) -> dict:
    """记录一次成功识别的模型类型和耗时。"""
    try:
        stats = _read_usage_stats()
        stats["total"] = stats.get("total", 0) + 1
        model_stats = stats["models"].setdefault(model, {"count": 0, "elapsed": 0.0})
        model_stats["count"] += 1
        model_stats["elapsed"] += elapsed
        with open(_STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f)
        return stats
    except Exception:
        return {}


def get_usage() -> int:
    """读取当前累计使用次数。"""
    return _read_usage_stats().get("total", 0)


def get_model_usage() -> dict:
    """读取按模型统计的成功调用次数和累计耗时。"""
    return _read_usage_stats()["models"]


# ──────────────────────────────────────────────────────────────
# SimpleTex API
# ──────────────────────────────────────────────────────────────

_SIMPLETEX_API_URLS = {
    "standard": "https://server.simpletex.cn/api/latex_ocr",
    "turbo": "https://server.simpletex.cn/api/latex_ocr_turbo",
}
_SIGN_CHARS = string.ascii_letters + string.digits


@dataclass
class RecognitionResult:
    latex: str
    confidence: float | None
    request_id: str | None


def _simpletex_credentials() -> tuple[str | None, str | None]:
    """从环境变量或 Streamlit secrets 读取 SimpleTex APP 凭据。"""
    app_id = os.getenv("SIMPLETEX_APP_ID")
    app_secret = os.getenv("SIMPLETEX_APP_SECRET")
    if app_id and app_secret:
        return app_id, app_secret

    try:
        return st.secrets.get("SIMPLETEX_APP_ID"), st.secrets.get("SIMPLETEX_APP_SECRET")
    except FileNotFoundError:
        return app_id, app_secret


def _simpletex_headers(data: dict[str, object], app_id: str, app_secret: str) -> dict[str, str]:
    """按 SimpleTex APP 鉴权规范生成请求头。"""
    headers = {
        "app-id": app_id,
        "random-str": "".join(secrets.choice(_SIGN_CHARS) for _ in range(16)),
        "timestamp": str(int(time.time())),
    }
    values = {**data, **headers}
    sign_source = "&".join(f"{key}={values[key]}" for key in sorted(values))
    headers["sign"] = hashlib.md5(f"{sign_source}&secret={app_secret}".encode()).hexdigest()
    return headers


def _simpletex_error(response: requests.Response, payload: dict) -> RuntimeError:
    error_type = payload.get("errType") or payload.get("error_type")
    messages = {
        "req_unauthorized": "鉴权失败，请检查 APP ID 与 APP Secret。",
        "resource_no_valid": "没有可用识别额度，请检查 SimpleTex 账户余额或资源包。",
        "image_missing": "未收到图片，请重新上传或粘贴。",
        "image_oversize": "图片过大，请压缩后重试。",
        "exceed_max_qps": "请求过于频繁，请稍后重试。",
        "exceed_max_ccy": "当前请求过多，请稍后重试。",
        "sever_closed": "SimpleTex 服务维护中，请稍后重试。",
        "server_inference_error": "SimpleTex 推理失败，请重新识别或切换模型。",
        "image_proc_error": "图片处理失败，请换一张清晰的图片重试。",
    }
    message = messages.get(error_type) or {
        401: "鉴权失败，请检查 APP ID 与 APP Secret。",
        402: "没有可用识别额度，请检查 SimpleTex 账户余额或资源包。",
        413: "图片缺失或过大，请重新上传或压缩后重试。",
        429: "请求过于频繁，请稍后重试。",
        503: "SimpleTex 服务维护中，请稍后重试。",
    }.get(response.status_code, f"SimpleTex 识别失败（HTTP {response.status_code}）。")
    request_id = payload.get("request_id")
    if request_id:
        message += f" 请求 ID：{request_id}"
    return RuntimeError(message)


def run_simpletex(image: Image.Image, model: str = "standard") -> RecognitionResult:
    """调用指定的 SimpleTex 公式识别模型，返回 LaTeX 字符串。"""
    try:
        api_url = _SIMPLETEX_API_URLS[model]
    except KeyError as exc:
        raise ValueError(f"不支持的 SimpleTex 模型：{model}") from exc

    app_id, app_secret = _simpletex_credentials()
    if not app_id or not app_secret:
        raise RuntimeError(
            "未配置 SimpleTex 凭据。请设置 SIMPLETEX_APP_ID 和 SIMPLETEX_APP_SECRET。"
        )

    image_bytes = io.BytesIO()
    image.save(image_bytes, format="PNG")
    data: dict[str, object] = {}
    try:
        response = requests.post(
            api_url,
            data=data,
            files={"file": ("formula.png", image_bytes.getvalue(), "image/png")},
            headers=_simpletex_headers(data, app_id, app_secret),
            timeout=30,
        )
    except requests.Timeout as exc:
        raise RuntimeError("连接 SimpleTex 超时，请稍后重新识别。") from exc
    except requests.RequestException as exc:
        raise RuntimeError("无法连接 SimpleTex，请检查网络后重试。") from exc
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"SimpleTex 返回了无效响应（HTTP {response.status_code}）。") from exc

    if not isinstance(payload, dict):
        raise RuntimeError(f"SimpleTex 返回了无效响应（HTTP {response.status_code}）。")
    if not response.ok or not payload.get("status"):
        raise _simpletex_error(response, payload)

    latex = payload.get("res", {}).get("latex")
    if not latex:
        raise RuntimeError("SimpleTex 未返回 LaTeX 结果。")
    confidence = payload["res"].get("conf")
    return RecognitionResult(
        latex=latex,
        confidence=confidence if isinstance(confidence, (int, float)) else None,
        request_id=payload.get("request_id"),
    )
