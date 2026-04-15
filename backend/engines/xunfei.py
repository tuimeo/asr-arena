import asyncio
import base64
import hashlib
import hmac
import json
from datetime import datetime, timezone
from urllib.parse import urlencode, urlparse

import websockets

from .base import ASRResult, BaseASREngine


def _build_auth_url(wss_url: str, api_key: str, api_secret: str) -> str:
    """Build authenticated WebSocket URL using HMAC-SHA256."""
    url = urlparse(wss_url)
    date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")

    signature_origin = (
        f"host: {url.hostname}\ndate: {date}\nGET {url.path} HTTP/1.1"
    )
    signature_sha = hmac.new(
        api_secret.encode(), signature_origin.encode(), hashlib.sha256
    ).digest()
    signature = base64.b64encode(signature_sha).decode()

    authorization_origin = (
        f'api_key="{api_key}", algorithm="hmac-sha256", '
        f'headers="host date request-line", signature="{signature}"'
    )
    authorization = base64.b64encode(authorization_origin.encode()).decode()

    params = {"authorization": authorization, "date": date, "host": url.hostname}
    return f"{wss_url}?{urlencode(params)}"


def _extract_text_from_ws(ws_list: list) -> str:
    """Extract text from ws[] array."""
    return "".join(cw.get("w", "") for w in ws_list for cw in w.get("cw", []))


class _WpgsCollector:
    """Handles wpgs (dynamic correction) protocol: apd=append, rpl=replace."""

    def __init__(self):
        self.sentences = []  # list of sentence strings, indexed by sn

    def process(self, pgs: str, rg: list, sn: int, text: str):
        # Ensure list is long enough
        while len(self.sentences) <= sn:
            self.sentences.append("")

        if pgs == "rpl" and len(rg) == 2:
            # Replace: clear range [rg[0], rg[1]] and set current
            start, end = rg
            for i in range(start, min(end + 1, len(self.sentences))):
                self.sentences[i] = ""
            self.sentences[sn] = text
        else:
            # Append
            self.sentences[sn] = text

    def get_text(self) -> str:
        return "".join(self.sentences)


class XunfeiIatEngine(BaseASREngine):
    """讯飞语音听写（旧版）"""
    engine_id = "xunfei_iat"
    display_name = "讯飞 语音听写"
    provider = "xunfei"

    WSS_URL = "wss://iat-api.xfyun.cn/v2/iat"

    async def recognize(self, wav_bytes: bytes, pcm_bytes: bytes, sample_rate: int, keys: dict) -> ASRResult:
        app_id = keys.get("app_id", "")
        api_key = keys.get("api_key", "")
        api_secret = keys.get("api_secret", "")
        if not all([app_id, api_key, api_secret]):
            return ASRResult(error="缺少 app_id / api_key / api_secret")

        ws_url = _build_auth_url(self.WSS_URL, api_key, api_secret)
        FRAME_SIZE = 1280
        collector = _WpgsCollector()

        try:
            async with websockets.connect(ws_url) as ws:
                total = len(pcm_bytes)
                offset = 0
                frame_idx = 0

                while offset < total:
                    end = min(offset + FRAME_SIZE, total)
                    chunk = pcm_bytes[offset:end]
                    is_first = frame_idx == 0
                    is_last = end >= total
                    status = 0 if is_first else (2 if is_last else 1)

                    data = {}
                    if is_first:
                        data["common"] = {"app_id": app_id}
                        data["business"] = {
                            "language": "zh_cn",
                            "domain": "iat",
                            "accent": "mandarin",
                            "vad_eos": 3000,
                            "dwa": "wpgs",
                            "ptt": 1,
                        }
                    data["data"] = {
                        "status": status,
                        "format": "audio/L16;rate=16000",
                        "encoding": "raw",
                        "audio": base64.b64encode(chunk).decode(),
                    }

                    await ws.send(json.dumps(data))
                    offset = end
                    frame_idx += 1
                    if not is_last:
                        await asyncio.sleep(0.013)  # ~3x realtime (40ms chunk / 3)

                while True:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=10)
                    except asyncio.TimeoutError:
                        break

                    resp = json.loads(msg)
                    code = resp.get("code", -1)
                    if code != 0:
                        return ASRResult(error=f"API 错误 ({code}): {resp.get('message', '')}")

                    resp_data = resp.get("data", {})
                    result = resp_data.get("result", {})
                    sn = result.get("sn", 0)
                    pgs = result.get("pgs", "")
                    rg = result.get("rg", [])
                    text_piece = _extract_text_from_ws(result.get("ws", []))

                    collector.process(pgs, rg, sn, text_piece)

                    if resp_data.get("status") == 2:
                        break

        except Exception as e:
            return ASRResult(error=f"讯飞语音听写错误: {type(e).__name__}: {e}")

        text = collector.get_text()
        return ASRResult(text=text if text else None)


class XunfeiSparkEngine(BaseASREngine):
    """讯飞星火中英识别大模型 — WebSocket, domain=slm"""
    engine_id = "xunfei_spark"
    display_name = "讯飞 星火语音大模型"
    provider = "xunfei"

    WSS_URL = "wss://iat.xf-yun.com/v1"

    async def recognize(self, wav_bytes: bytes, pcm_bytes: bytes, sample_rate: int, keys: dict) -> ASRResult:
        app_id = keys.get("app_id", "")
        api_key = keys.get("api_key", "")
        api_secret = keys.get("api_secret", "")
        if not all([app_id, api_key, api_secret]):
            return ASRResult(error="缺少 app_id / api_key / api_secret")

        ws_url = _build_auth_url(self.WSS_URL, api_key, api_secret)
        FRAME_SIZE = 1280
        collector = _WpgsCollector()

        try:
            async with websockets.connect(ws_url) as ws:
                total = len(pcm_bytes)
                offset = 0
                seq = 0

                while offset < total:
                    end = min(offset + FRAME_SIZE, total)
                    chunk = pcm_bytes[offset:end]
                    is_first = seq == 0
                    is_last = end >= total
                    status = 0 if is_first else (2 if is_last else 1)

                    data = {}
                    if is_first:
                        data["header"] = {"app_id": app_id, "status": 0}
                        data["parameter"] = {
                            "iat": {
                                "domain": "slm",
                                "language": "zh_cn",
                                "accent": "mandarin",
                                "eos": 6000,
                                "vinfo": 1,
                                "dwa": "wpgs",
                                "result": {
                                    "encoding": "utf8",
                                    "compress": "raw",
                                    "format": "json",
                                },
                            }
                        }
                    else:
                        data["header"] = {"app_id": app_id, "status": status}

                    data["payload"] = {
                        "audio": {
                            "encoding": "raw",
                            "sample_rate": 16000,
                            "channels": 1,
                            "bit_depth": 16,
                            "seq": seq,
                            "status": status,
                            "audio": base64.b64encode(chunk).decode(),
                        }
                    }

                    await ws.send(json.dumps(data))
                    offset = end
                    seq += 1
                    if not is_last:
                        await asyncio.sleep(0.013)  # ~3x realtime (40ms chunk / 3)

                while True:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=10)
                    except asyncio.TimeoutError:
                        break

                    resp = json.loads(msg)
                    header = resp.get("header", {})
                    code = header.get("code", resp.get("code", -1))
                    if code != 0:
                        message = header.get("message", resp.get("message", ""))
                        return ASRResult(error=f"API 错误 ({code}): {message}")

                    payload = resp.get("payload", resp.get("data", {}))
                    result = payload.get("result", {})

                    # Result text may be base64-encoded JSON
                    if "text" in result and isinstance(result["text"], str):
                        try:
                            decoded = json.loads(base64.b64decode(result["text"]).decode())
                            sn = decoded.get("sn", 0)
                            pgs = decoded.get("pgs", "")
                            rg = decoded.get("rg", [])
                            text_piece = _extract_text_from_ws(decoded.get("ws", []))
                        except Exception:
                            sn = result.get("sn", 0)
                            pgs = ""
                            rg = []
                            text_piece = result["text"]
                    else:
                        sn = result.get("sn", 0)
                        pgs = result.get("pgs", "")
                        rg = result.get("rg", [])
                        text_piece = _extract_text_from_ws(result.get("ws", []))

                    collector.process(pgs, rg, sn, text_piece)

                    resp_status = header.get("status", payload.get("status", -1))
                    if resp_status == 2:
                        break

        except Exception as e:
            return ASRResult(error=f"讯飞星火错误: {type(e).__name__}: {e}")

        text = collector.get_text()
        return ASRResult(text=text if text else None)
