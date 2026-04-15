import asyncio
import base64
import os
import tempfile
import threading
import time

from .base import ASRResult, BaseASREngine


class _AliRecognitionEngine(BaseASREngine):
    """Base for DashScope Recognition-based engines (paraformer, fun-asr)."""
    provider = "ali"
    model: str = ""

    async def recognize(self, wav_bytes: bytes, pcm_bytes: bytes, sample_rate: int, keys: dict) -> ASRResult:
        api_key = keys.get("api_key", "")
        if not api_key:
            return ASRResult(error="缺少 api_key")

        model = self.model

        def _call():
            import dashscope
            from dashscope.audio.asr import Recognition, RecognitionCallback

            dashscope.api_key = api_key

            callback = RecognitionCallback()
            recognition = Recognition(
                model=model,
                callback=callback,
                format="wav",
                sample_rate=sample_rate,
            )

            # Recognition.call() only accepts file path
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                f.write(wav_bytes)
                tmp_path = f.name

            try:
                result = recognition.call(file=tmp_path)
                if result.status_code == 200:
                    sentences = result.get_sentence()
                    if sentences and isinstance(sentences, list):
                        text = "".join(s.get("text", "") for s in sentences)
                    elif sentences and isinstance(sentences, dict):
                        text = sentences.get("text", "")
                    else:
                        text = ""
                    return ASRResult(text=text if text else None)
                else:
                    return ASRResult(error=f"API 错误 ({result.status_code}): {result.message}")
            finally:
                os.unlink(tmp_path)

        return await asyncio.to_thread(_call)


class AliParaformerEngine(_AliRecognitionEngine):
    engine_id = "ali_paraformer"
    display_name = "阿里云 Paraformer-v2"
    model = "paraformer-realtime-v2"


class AliFunASREngine(_AliRecognitionEngine):
    engine_id = "ali_funasr"
    display_name = "阿里云 Fun-ASR"
    model = "fun-asr-realtime"


class AliQwen3ASREngine(BaseASREngine):
    """Qwen3-ASR uses MultiModalConversation API with base64 audio."""
    engine_id = "ali_qwen3asr"
    display_name = "阿里云 Qwen3-ASR"
    provider = "ali"

    async def recognize(self, wav_bytes: bytes, pcm_bytes: bytes, sample_rate: int, keys: dict) -> ASRResult:
        api_key = keys.get("api_key", "")
        if not api_key:
            return ASRResult(error="缺少 api_key")

        def _call():
            import dashscope

            b64 = base64.b64encode(wav_bytes).decode()
            audio_uri = f"data:audio/wav;base64,{b64}"

            response = dashscope.MultiModalConversation.call(
                api_key=api_key,
                model="qwen3-asr-flash",
                messages=[
                    {"role": "user", "content": [{"audio": audio_uri}]},
                ],
                result_format="message",
            )

            if response.status_code == 200:
                content = response.output.choices[0].message.content
                if isinstance(content, list) and len(content) > 0:
                    text = content[0].get("text", "")
                elif isinstance(content, str):
                    text = content
                else:
                    text = ""
                return ASRResult(text=text if text else None)
            else:
                return ASRResult(error=f"API 错误 ({response.status_code}): {response.message}")

        return await asyncio.to_thread(_call)


class AliQwen3ASRRealtimeEngine(BaseASREngine):
    """Qwen3-ASR-Realtime uses OmniRealtimeConversation API with streaming PCM."""
    engine_id = "ali_qwen3asr_realtime"
    display_name = "阿里云 Qwen3-ASR-Realtime"
    provider = "ali"

    async def recognize(self, wav_bytes: bytes, pcm_bytes: bytes, sample_rate: int, keys: dict) -> ASRResult:
        api_key = keys.get("api_key", "")
        if not api_key:
            return ASRResult(error="缺少 api_key")

        def _call():
            import dashscope
            from dashscope.audio.qwen_omni import OmniRealtimeConversation, OmniRealtimeCallback, MultiModality
            from dashscope.audio.qwen_omni.omni_realtime import TranscriptionParams

            dashscope.api_key = api_key
            final_text = []
            done = threading.Event()
            error_msg = [None]

            class Callback(OmniRealtimeCallback):
                def on_event(self, response):
                    if response.get("type") == "conversation.item.input_audio_transcription.completed":
                        final_text.append(response.get("transcript", ""))
                        done.set()

                def on_close(self, code, msg):
                    done.set()

                def on_error(self, response):
                    error_msg[0] = str(response)
                    done.set()

                def on_open(self):
                    pass

            conversation = OmniRealtimeConversation(
                model="qwen3-asr-flash-realtime",
                url="wss://dashscope.aliyuncs.com/api-ws/v1/realtime",
                callback=Callback(),
            )
            conversation.connect()

            transcription_params = TranscriptionParams(
                language="zh",
                sample_rate=sample_rate,
                input_audio_format="pcm",
            )
            conversation.update_session(
                output_modalities=[MultiModality.TEXT],
                enable_input_audio_transcription=True,
                transcription_params=transcription_params,
            )

            # Send PCM in chunks
            chunk_size = 3200  # 100ms at 16kHz 16-bit mono
            for i in range(0, len(pcm_bytes), chunk_size):
                chunk = pcm_bytes[i:i + chunk_size]
                audio_b64 = base64.b64encode(chunk).decode("ascii")
                conversation.append_audio(audio_b64)
                time.sleep(0.033)  # ~3x realtime (100ms chunk / 3)

            conversation.end_session()
            done.wait(timeout=15)
            conversation.close()

            if error_msg[0]:
                return ASRResult(error=f"实时识别错误: {error_msg[0]}")

            text = "".join(final_text)
            return ASRResult(text=text if text else None)

        return await asyncio.to_thread(_call)
