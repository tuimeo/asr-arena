import asyncio
import base64
import hashlib
import hmac
import time

import requests

from .base import ASRResult, BaseASREngine

TENCENT_HTTP_TIMEOUT_SECONDS = 55


class TencentSentenceEngine(BaseASREngine):
    """腾讯云一句话识别 — SentenceRecognition API, 同步, ≤60s"""
    engine_id = "tencent_sentence"
    display_name = "腾讯云 一句话识别"
    provider = "tencent"

    async def recognize(self, wav_bytes: bytes, pcm_bytes: bytes, sample_rate: int, keys: dict) -> ASRResult:
        secret_id = keys.get("secret_id", "")
        secret_key = keys.get("secret_key", "")
        if not all([secret_id, secret_key]):
            return ASRResult(error="缺少 secret_id / secret_key")

        def _call():
            from tencentcloud.common import credential
            from tencentcloud.common.profile.client_profile import ClientProfile
            from tencentcloud.common.profile.http_profile import HttpProfile
            from tencentcloud.asr.v20190614 import asr_client, models

            cred = credential.Credential(secret_id, secret_key)
            http_profile = HttpProfile(reqTimeout=TENCENT_HTTP_TIMEOUT_SECONDS)
            client_profile = ClientProfile(httpProfile=http_profile)
            client = asr_client.AsrClient(cred, "", client_profile)

            req = models.SentenceRecognitionRequest()
            req.EngSerViceType = "16k_zh"
            req.SourceType = 1
            req.VoiceFormat = "wav"
            req.Data = base64.b64encode(wav_bytes).decode()
            req.DataLen = len(wav_bytes)

            resp = client.SentenceRecognition(req)
            text = resp.Result
            return ASRResult(text=text if text else None)

        return await asyncio.to_thread(_call)


class _TencentFlashEngine(BaseASREngine):
    """Base for Tencent Flash Recognition (极速版).
    Uses the same signing logic as the official tencentcloud-speech-sdk-python.
    """
    provider = "tencent"
    engine_type: str = "16k_zh"

    def _build_sign_string(self, appid: str, sorted_params: list[tuple]) -> str:
        """Replicate the official SDK's _format_sign_string:
        appid goes in the path, not in the query string."""
        sign_str = f"POSTasr.cloud.tencent.com/asr/flash/v1/{appid}?"
        parts = []
        for key, value in sorted_params:
            if key == "appid":
                continue
            parts.append(f"{key}={value}")
        sign_str += "&".join(parts)
        return sign_str

    async def recognize(self, wav_bytes: bytes, pcm_bytes: bytes, sample_rate: int, keys: dict) -> ASRResult:
        secret_id = keys.get("secret_id", "")
        secret_key = keys.get("secret_key", "")
        appid = keys.get("appid", "")
        if not all([secret_id, secret_key, appid]):
            return ASRResult(error="缺少 secret_id / secret_key / appid")

        engine_type = self.engine_type

        def _call():
            timestamp = str(int(time.time()))
            params = {
                "appid": appid,
                "secretid": secret_id,
                "timestamp": timestamp,
                "engine_type": engine_type,
                "voice_format": "wav",
                "speaker_diarization": 0,
                "filter_dirty": 0,
                "filter_modal": 0,
                "filter_punc": 0,
                "convert_num_mode": 1,
                "word_info": 0,
                "first_channel_only": 1,
                "reinforce_hotword": 0,
                "sentence_max_length": 0,
            }

            sorted_params = sorted(params.items(), key=lambda d: d[0])
            sign_str = self._build_sign_string(appid, sorted_params)
            signature = base64.b64encode(
                hmac.new(secret_key.encode(), sign_str.encode(), hashlib.sha1).digest()
            ).decode()

            # Build URL from sign string (strip "POST", add "https://")
            req_url = "https://" + sign_str[4:]
            headers = {
                "Host": "asr.cloud.tencent.com",
                "Authorization": signature,
            }

            resp = requests.post(
                req_url,
                headers=headers,
                data=wav_bytes,
                timeout=TENCENT_HTTP_TIMEOUT_SECONDS,
            )
            data = resp.json()

            if data.get("code") != 0:
                return ASRResult(error=f"API 错误 ({data.get('code')}): {data.get('message', '')}")

            flash_result = data.get("flash_result", [])
            text = "".join(item.get("text", "") for item in flash_result)
            return ASRResult(text=text if text else None)

        return await asyncio.to_thread(_call)


class TencentFlashEngine(_TencentFlashEngine):
    engine_id = "tencent_flash"
    display_name = "腾讯云 极速版"
    engine_type = "16k_zh"


class TencentFlashLargeEngine(_TencentFlashEngine):
    engine_id = "tencent_flash_large"
    display_name = "腾讯云 极速版(大模型)"
    engine_type = "16k_zh_large"
