import os
import io
import json
import base64
import hashlib
import secrets
import string
import time
from pathlib import Path

import requests
import streamlit as st
from dotenv import load_dotenv
from PIL import Image

load_dotenv()


# ──────────────────────────────────────────────────────────────
# 图片工具
# ──────────────────────────────────────────────────────────────

def base64_to_image(data_url: str) -> Image.Image:
    """将剪贴板组件返回的 base64 data URL 转换为 PIL Image。"""
    _, data = data_url.split(",", 1)
    img_bytes = base64.b64decode(data)
    return Image.open(io.BytesIO(img_bytes)).convert("RGB")


# ──────────────────────────────────────────────────────────────
# 使用次数统计
# ──────────────────────────────────────────────────────────────
_STATS_FILE = Path(__file__).parent / "usage_stats.json"


def increment_usage():
    """每次模型调用成功后调用，累加计数并写入本地文件。"""
    try:
        stats = {"total": 0}
        if _STATS_FILE.exists():
            with open(_STATS_FILE, "r", encoding="utf-8") as f:
                stats = json.load(f)
        stats["total"] = stats.get("total", 0) + 1
        with open(_STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f)
        return stats["total"]
    except Exception:
        return 0


def get_usage() -> int:
    """读取当前累计使用次数。"""
    try:
        if _STATS_FILE.exists():
            with open(_STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f).get("total", 0)
    except Exception:
        pass
    return 0


# ──────────────────────────────────────────────────────────────
# SimpleTex API
# ──────────────────────────────────────────────────────────────

_SIMPLETEX_API_URLS = {
    "standard": "https://server.simpletex.cn/api/latex_ocr",
    "turbo": "https://server.simpletex.cn/api/latex_ocr_turbo",
}
_SIGN_CHARS = string.ascii_letters + string.digits


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


def run_simpletex(image: Image.Image, model: str = "standard") -> str:
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
    response = requests.post(
        api_url,
        data=data,
        files={"file": ("formula.png", image_bytes.getvalue(), "image/png")},
        headers=_simpletex_headers(data, app_id, app_secret),
        timeout=30,
    )
    try:
        payload = response.json()
    except ValueError as exc:
        raise RuntimeError(f"SimpleTex 返回了无效响应（HTTP {response.status_code}）。") from exc

    if not response.ok or not payload.get("status"):
        detail = payload.get("message") or payload.get("errType") or response.reason
        request_id = payload.get("request_id")
        suffix = f"（请求 ID：{request_id}）" if request_id else ""
        raise RuntimeError(f"SimpleTex 识别失败：{detail}{suffix}")

    latex = payload.get("res", {}).get("latex")
    if not latex:
        raise RuntimeError("SimpleTex 未返回 LaTeX 结果。")
    return latex
