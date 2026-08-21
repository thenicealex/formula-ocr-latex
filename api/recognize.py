import base64
import hashlib
import json
import secrets
import string
import time
from http.server import BaseHTTPRequestHandler

import requests


# JSON/base64 expands an image by roughly one third. Keep the full request below
# Vercel Functions' 4.5 MB payload limit.
MAX_IMAGE_BYTES = 3 * 1024 * 1024
IMAGE_TYPES = {
    "image/png": ("formula.png", "image/png"),
    "image/jpeg": ("formula.jpg", "image/jpeg"),
    "image/webp": ("formula.webp", "image/webp"),
}
SIMPLETEX_API_URLS = {
    "standard": "https://server.simpletex.cn/api/latex_ocr",
    "turbo": "https://server.simpletex.cn/api/latex_ocr_turbo",
}
SIGN_CHARS = string.ascii_letters + string.digits


def simpletex_headers(data: dict, app_id: str, app_secret: str) -> dict[str, str]:
    headers = {
        "app-id": app_id,
        "random-str": "".join(secrets.choice(SIGN_CHARS) for _ in range(16)),
        "timestamp": str(int(time.time())),
    }
    values = {**data, **headers}
    sign_source = "&".join(f"{key}={values[key]}" for key in sorted(values))
    headers["sign"] = hashlib.md5(
        f"{sign_source}&secret={app_secret}".encode()
    ).hexdigest()
    return headers


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/api/recognize":
            self.respond(404, {"error": "Not found."})
            return

        try:
            content_length = int(self.headers.get("Content-Length", "0"))
            if not 0 < content_length <= MAX_IMAGE_BYTES * 2:
                raise ValueError("图片过大或请求无效。")
            body = json.loads(self.rfile.read(content_length))
            app_id = body["appId"].strip()
            app_secret = body["appSecret"].strip()
            model = body.get("model", "standard")
            image_type = body["imageType"]
            image = base64.b64decode(body["image"], validate=True)
            if not app_id or not app_secret:
                raise ValueError("请填写 SimpleTex APP ID 与 APP Secret。")
            if model not in SIMPLETEX_API_URLS:
                raise ValueError("不支持的识别模型。")
            if image_type not in IMAGE_TYPES:
                raise ValueError("不支持的图片格式。")
            if not 0 < len(image) <= MAX_IMAGE_BYTES:
                raise ValueError("图片不能超过 3 MB。")
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            self.respond(400, {"error": str(exc) or "请求格式无效。"})
            return

        try:
            response = requests.post(
                SIMPLETEX_API_URLS[model],
                data={},
                files={"file": (IMAGE_TYPES[image_type][0], image, IMAGE_TYPES[image_type][1])},
                headers=simpletex_headers({}, app_id, app_secret),
                timeout=25,
            )
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError
        except requests.Timeout:
            self.respond(504, {"error": "连接 SimpleTex 超时，请稍后重新识别。"})
            return
        except (requests.RequestException, ValueError):
            self.respond(502, {"error": "SimpleTex 返回了无效响应，请稍后重试。"})
            return

        if not response.ok or not payload.get("status"):
            self.respond(response.status_code or 502, {"error": simpletex_error(response.status_code, payload)})
            return

        result = payload.get("res", {})
        latex = result.get("latex")
        if not latex:
            self.respond(502, {"error": "SimpleTex 未返回 LaTeX 结果。"})
            return
        self.respond(200, {
            "latex": latex,
            "confidence": result.get("conf"),
            "requestId": payload.get("request_id"),
        })

    def respond(self, status: int, payload: dict):
        encoded = json.dumps(payload, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)


def simpletex_error(status: int, payload: dict) -> str:
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
    return messages.get(payload.get("errType") or payload.get("error_type"), {
        401: "鉴权失败，请检查 APP ID 与 APP Secret。",
        402: "没有可用识别额度，请检查 SimpleTex 账户余额或资源包。",
        413: "图片缺失或过大，请重新上传或压缩后重试。",
        429: "请求过于频繁，请稍后重试。",
        503: "SimpleTex 服务维护中，请稍后重试。",
    }.get(status, f"SimpleTex 识别失败（HTTP {status}）。"))
