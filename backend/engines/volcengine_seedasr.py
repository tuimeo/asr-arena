import asyncio
import gzip
import json
import uuid

import websockets

from .base import ASRResult, BaseASREngine

# ── Volcengine binary protocol constants ──────────────────────────────
PROTOCOL_VERSION = 0b0001
DEFAULT_HEADER_SIZE = 0b0001

# Message types (upper 4 bits of byte 1)
FULL_CLIENT_REQUEST = 0b0001
AUDIO_ONLY_REQUEST  = 0b0010
FULL_SERVER_RESPONSE = 0b1001
SERVER_ACK           = 0b1011
SERVER_ERROR_RESPONSE = 0b1111

# Sequence flags (lower 4 bits of byte 1)
NO_SEQUENCE    = 0b0000
POS_SEQUENCE   = 0b0001
NEG_SEQUENCE   = 0b0010
NEG_WITH_SEQ   = 0b0011

# Serialization (upper 4 bits of byte 2)
NO_SERIALIZATION = 0b0000
JSON_SERIAL      = 0b0001

# Compression (lower 4 bits of byte 2)
NO_COMPRESSION = 0b0000
GZIP_COMPRESS  = 0b0001


def _build_header(
    message_type=FULL_CLIENT_REQUEST,
    flags=NO_SEQUENCE,
    serial_method=JSON_SERIAL,
    compression=GZIP_COMPRESS,
):
    """Build the 4-byte binary protocol header."""
    header = bytearray(4)
    header[0] = (PROTOCOL_VERSION << 4) | DEFAULT_HEADER_SIZE
    header[1] = (message_type << 4) | flags
    header[2] = (serial_method << 4) | compression
    header[3] = 0x00  # reserved
    return header


def _parse_response(data: bytes) -> dict:
    """Parse a binary response from the server."""
    if len(data) < 4:
        return {"error": "response too short"}

    message_type = (data[1] >> 4) & 0x0F
    flags = data[1] & 0x0F
    serial_method = (data[2] >> 4) & 0x0F
    compression = data[2] & 0x0F
    header_size = data[0] & 0x0F  # in 4-byte units

    result = {"is_last_package": False, "payload_msg": None}

    payload = data[header_size * 4:]

    # Extract sequence if present
    if flags & 0x01:
        if len(payload) >= 4:
            seq = int.from_bytes(payload[:4], "big", signed=True)
            result["sequence"] = seq
            payload = payload[4:]

    if flags & 0x02:
        result["is_last_package"] = True

    if message_type == SERVER_ERROR_RESPONSE:
        if len(payload) >= 4:
            payload_size = int.from_bytes(payload[:4], "big", signed=True)
            payload_body = payload[4:4 + payload_size] if payload_size > 0 else b""
            if compression == GZIP_COMPRESS and payload_body:
                try:
                    payload_body = gzip.decompress(payload_body)
                except Exception:
                    pass
            try:
                result["payload_msg"] = json.loads(payload_body.decode("utf-8"))
            except Exception:
                result["payload_msg"] = {"raw": payload_body.hex()}
        result["error"] = True
        return result

    if message_type == FULL_SERVER_RESPONSE:
        if len(payload) >= 4:
            payload_size = int.from_bytes(payload[:4], "big", signed=True)
            payload_body = payload[4:4 + payload_size] if payload_size > 0 else b""
        else:
            payload_body = b""

        if compression == GZIP_COMPRESS and payload_body:
            try:
                payload_body = gzip.decompress(payload_body)
            except Exception:
                pass

        if serial_method == JSON_SERIAL and payload_body:
            try:
                result["payload_msg"] = json.loads(payload_body.decode("utf-8"))
            except Exception:
                result["payload_msg"] = {"raw": payload_body.hex()}
        else:
            result["payload_msg"] = payload_body

    return result


class _VolcengineASREngine(BaseASREngine):
    """Base for Volcengine Seed-ASR engines. Subclasses set wss_url and resource_id."""
    provider = "volcengine"
    wss_url: str = ""
    resource_id: str = ""
    enable_nonstream: bool = False  # 2.0 bidirectional streaming only

    async def recognize(self, wav_bytes: bytes, pcm_bytes: bytes, sample_rate: int, keys: dict) -> ASRResult:
        app_id = keys.get("app_id", "")
        access_token = keys.get("access_token", "")
        if not all([app_id, access_token]):
            return ASRResult(error="缺少 app_id / access_token")

        request_id = str(uuid.uuid4())

        # Authentication via HTTP headers
        ws_headers = {
            "X-Api-Resource-Id": self.resource_id,
            "X-Api-Access-Key": access_token,
            "X-Api-App-Key": app_id,
            "X-Api-Connect-Id": request_id,
        }

        # Build the full_client_request (initial config)
        request_params = {
            "user": {"uid": request_id},
            "audio": {
                "format": "pcm",
                "rate": sample_rate,
                "bits": 16,
                "channel": 1,
                "codec": "raw",
            },
            "request": {
                "model_name": "bigmodel",
                "enable_punc": True,
                "result_type": "full",
            },
        }
        if self.enable_nonstream:
            request_params["request"]["enable_nonstream"] = True

        payload_bytes = gzip.compress(json.dumps(request_params).encode("utf-8"))

        full_client_req = bytearray(_build_header(
            message_type=FULL_CLIENT_REQUEST,
            flags=POS_SEQUENCE,
            serial_method=JSON_SERIAL,
            compression=GZIP_COMPRESS,
        ))
        full_client_req.extend((1).to_bytes(4, "big", signed=True))
        full_client_req.extend(len(payload_bytes).to_bytes(4, "big"))
        full_client_req.extend(payload_bytes)

        FRAME_SIZE = 6400  # 200ms at 16kHz 16-bit mono (recommended by docs)
        full_text = ""

        try:
            async with websockets.connect(
                self.wss_url,
                additional_headers=ws_headers,
                max_size=1_000_000_000,
            ) as ws:
                # Send initial config
                await ws.send(bytes(full_client_req))
                resp = await asyncio.wait_for(ws.recv(), timeout=10)
                init_result = _parse_response(resp)
                if init_result.get("error"):
                    msg = init_result.get("payload_msg", {})
                    return ASRResult(error=f"连接错误: {msg}")

                # Send audio chunks
                offset = 0
                seq = 2
                while offset < len(pcm_bytes):
                    end = min(offset + FRAME_SIZE, len(pcm_bytes))
                    chunk = pcm_bytes[offset:end]
                    is_last = (end >= len(pcm_bytes))

                    compressed_chunk = gzip.compress(chunk)

                    if is_last:
                        audio_req = bytearray(_build_header(
                            message_type=AUDIO_ONLY_REQUEST,
                            flags=NEG_WITH_SEQ,
                            serial_method=NO_SERIALIZATION,
                            compression=GZIP_COMPRESS,
                        ))
                        audio_req.extend((-seq).to_bytes(4, "big", signed=True))
                    else:
                        audio_req = bytearray(_build_header(
                            message_type=AUDIO_ONLY_REQUEST,
                            flags=POS_SEQUENCE,
                            serial_method=NO_SERIALIZATION,
                            compression=GZIP_COMPRESS,
                        ))
                        audio_req.extend(seq.to_bytes(4, "big", signed=True))

                    audio_req.extend(len(compressed_chunk).to_bytes(4, "big"))
                    audio_req.extend(compressed_chunk)

                    await ws.send(bytes(audio_req))
                    seq += 1
                    offset = end

                    if not is_last:
                        await asyncio.sleep(0.067)  # ~3x realtime (200ms chunk / 3)

                # Collect results
                while True:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=15)
                    except asyncio.TimeoutError:
                        break

                    result = _parse_response(msg)

                    if result.get("error"):
                        err_msg = result.get("payload_msg", {})
                        return ASRResult(error=f"API 错误: {err_msg}")

                    payload = result.get("payload_msg")
                    if isinstance(payload, dict):
                        res = payload.get("result", {})
                        text = res.get("text", "")
                        if text:
                            full_text = text

                    if result.get("is_last_package"):
                        break

        except websockets.exceptions.InvalidStatusCode as e:
            return ASRResult(error=f"WebSocket 连接被拒绝: HTTP {e.status_code}")
        except websockets.exceptions.ConnectionClosed as e:
            return ASRResult(error=f"WebSocket 连接关闭: {e}")
        except Exception as e:
            return ASRResult(error=f"火山引擎 ASR 错误: {type(e).__name__}: {e}")

        return ASRResult(text=full_text if full_text else None)


class VolcengineSeedASREngine(_VolcengineASREngine):
    """Seed-ASR 1.0 双向流式"""
    engine_id = "volcengine_seedasr"
    display_name = "火山 Seed-ASR 1.0 流式"
    wss_url = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel"
    resource_id = "volc.bigasr.sauc.duration"


class VolcengineSeedASRNostreamEngine(_VolcengineASREngine):
    """Seed-ASR 1.0 流式输入 — 发完再返回，准确率更高"""
    engine_id = "volcengine_seedasr_nostream"
    display_name = "火山 Seed-ASR 1.0 非流式"
    wss_url = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_nostream"
    resource_id = "volc.bigasr.sauc.duration"


class VolcengineSeedASR2Engine(_VolcengineASREngine):
    """Seed-ASR 2.0 双向流式(优化版) + 二遍识别：流式上屏 + 分句用非流式模型重识别"""
    engine_id = "volcengine_seedasr2"
    display_name = "火山 Seed-ASR 2.0 流式"
    wss_url = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_async"
    resource_id = "volc.seedasr.sauc.duration"
    enable_nonstream = True


class VolcengineSeedASR2NostreamEngine(_VolcengineASREngine):
    """Seed-ASR 2.0 流式输入 — 发完再返回，准确率更高"""
    engine_id = "volcengine_seedasr2_nostream"
    display_name = "火山 Seed-ASR 2.0 非流式"
    wss_url = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_nostream"
    resource_id = "volc.seedasr.sauc.duration"
