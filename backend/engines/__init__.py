from .base import BaseASREngine, ASRResult
from .ali_dashscope import AliParaformerEngine, AliFunASREngine, AliQwen3ASREngine, AliQwen3ASRRealtimeEngine
from .baidu import BaiduStandardEngine, BaiduProEngine
from .xunfei import XunfeiIatEngine, XunfeiSparkEngine
from .tencent import TencentSentenceEngine, TencentFlashEngine, TencentFlashLargeEngine
from .volcengine_seedasr import (
    VolcengineSeedASREngine, VolcengineSeedASRNostreamEngine,
    VolcengineSeedASR2Engine, VolcengineSeedASR2NostreamEngine,
)

ENGINE_REGISTRY: dict[str, BaseASREngine] = {
    "ali_paraformer": AliParaformerEngine(),
    "ali_funasr": AliFunASREngine(),
    "ali_qwen3asr": AliQwen3ASREngine(),
    "ali_qwen3asr_realtime": AliQwen3ASRRealtimeEngine(),
    "baidu_standard": BaiduStandardEngine(),
    "baidu_pro": BaiduProEngine(),
    "xunfei_iat": XunfeiIatEngine(),
    "xunfei_spark": XunfeiSparkEngine(),
    "tencent_sentence": TencentSentenceEngine(),
    "tencent_flash": TencentFlashEngine(),
    "tencent_flash_large": TencentFlashLargeEngine(),
    "volcengine_seedasr": VolcengineSeedASREngine(),
    "volcengine_seedasr_nostream": VolcengineSeedASRNostreamEngine(),
    "volcengine_seedasr2": VolcengineSeedASR2Engine(),
    "volcengine_seedasr2_nostream": VolcengineSeedASR2NostreamEngine(),
}

__all__ = ["ENGINE_REGISTRY", "BaseASREngine", "ASRResult"]
