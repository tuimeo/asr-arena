import asyncio

from .base import ASRResult, BaseASREngine


class _BaiduEngine(BaseASREngine):
    """Base for Baidu ASR engines. Subclasses set dev_pid and api_url."""
    provider = "baidu"
    dev_pid: int = 1537
    api_url: str = "http://vop.baidu.com/server_api"

    async def recognize(self, wav_bytes: bytes, pcm_bytes: bytes, sample_rate: int, keys: dict) -> ASRResult:
        app_id = keys.get("app_id", "")
        api_key = keys.get("api_key", "")
        secret_key = keys.get("secret_key", "")
        if not all([app_id, api_key, secret_key]):
            return ASRResult(error="缺少 app_id / api_key / secret_key")

        dev_pid = self.dev_pid
        api_url = self.api_url

        def _call():
            from aip import AipSpeech

            client = AipSpeech(app_id, api_key, secret_key)
            client._AipSpeech__asrUrl = api_url
            result = client.asr(pcm_bytes, "pcm", sample_rate, {"dev_pid": dev_pid})
            if result.get("err_no") == 0:
                texts = result.get("result", [])
                return ASRResult(text="".join(texts) if texts else None)
            else:
                return ASRResult(error=f"API 错误 ({result.get('err_no')}): {result.get('err_msg')}")

        return await asyncio.to_thread(_call)


class BaiduStandardEngine(_BaiduEngine):
    engine_id = "baidu_standard"
    display_name = "百度 标准版"
    dev_pid = 1537
    api_url = "http://vop.baidu.com/server_api"


class BaiduProEngine(_BaiduEngine):
    engine_id = "baidu_pro"
    display_name = "百度 极速版"
    dev_pid = 80001
    api_url = "http://vop.baidu.com/pro_api"
