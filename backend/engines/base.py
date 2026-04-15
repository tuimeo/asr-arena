from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ASRResult:
    text: str | None = None
    error: str | None = None


class BaseASREngine(ABC):
    engine_id: str = ""
    display_name: str = ""
    provider: str = ""  # maps to keys dict key: "ali", "baidu", "xunfei", "tencent", "volcengine"

    @abstractmethod
    async def recognize(self, wav_bytes: bytes, pcm_bytes: bytes, sample_rate: int, keys: dict) -> ASRResult:
        """
        Recognize speech from audio.

        Args:
            wav_bytes: Complete WAV file bytes (16kHz 16-bit mono).
            pcm_bytes: Raw PCM bytes without WAV header.
            sample_rate: Sample rate in Hz (always 16000).
            keys: Provider-specific API keys dict.

        Returns:
            ASRResult with text or error.
        """
        ...
