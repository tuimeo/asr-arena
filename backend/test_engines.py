"""
开发测试脚本：用 .env 中的 key + 本地音频文件，直接测试各服务。
不走 HTTP，不走前端。

用法:
    uv run python -m backend.test_engines samples/test.wav
    uv run python -m backend.test_engines samples/test.wav --engines ali_paraformer,baidu_standard
    uv run python -m backend.test_engines samples/test.wav --reference "这是一段测试文本"
"""

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).parent.parent / ".env")

from backend.audio_utils import convert_to_pcm16k
from backend.cer_utils import calculate_cer
from backend.engines import ENGINE_REGISTRY


def get_env_keys() -> dict:
    """Read API keys from .env."""
    env_keys = {}

    if os.getenv("ALI_API_KEY"):
        env_keys["ali"] = {"api_key": os.getenv("ALI_API_KEY")}

    if os.getenv("BAIDU_APP_ID") and os.getenv("BAIDU_API_KEY") and os.getenv("BAIDU_SECRET_KEY"):
        env_keys["baidu"] = {
            "app_id": os.getenv("BAIDU_APP_ID"),
            "api_key": os.getenv("BAIDU_API_KEY"),
            "secret_key": os.getenv("BAIDU_SECRET_KEY"),
        }

    if os.getenv("XUNFEI_APP_ID") and os.getenv("XUNFEI_API_KEY") and os.getenv("XUNFEI_API_SECRET"):
        env_keys["xunfei"] = {
            "app_id": os.getenv("XUNFEI_APP_ID"),
            "api_key": os.getenv("XUNFEI_API_KEY"),
            "api_secret": os.getenv("XUNFEI_API_SECRET"),
        }

    if os.getenv("TENCENT_SECRET_ID") and os.getenv("TENCENT_SECRET_KEY"):
        tencent_keys = {
            "secret_id": os.getenv("TENCENT_SECRET_ID"),
            "secret_key": os.getenv("TENCENT_SECRET_KEY"),
        }
        if os.getenv("TENCENT_APPID"):
            tencent_keys["appid"] = os.getenv("TENCENT_APPID")
        env_keys["tencent"] = tencent_keys

    if os.getenv("VOLCENGINE_APP_ID") and os.getenv("VOLCENGINE_ACCESS_TOKEN"):
        env_keys["volcengine"] = {
            "app_id": os.getenv("VOLCENGINE_APP_ID"),
            "access_token": os.getenv("VOLCENGINE_ACCESS_TOKEN"),
        }

    return env_keys


async def test_engine(engine_id: str, wav_bytes: bytes, pcm_bytes: bytes, keys: dict, reference: str):
    engine = ENGINE_REGISTRY[engine_id]
    provider_keys = keys.get(engine.provider)
    if not provider_keys:
        print(f"  [{engine_id}] SKIP - .env 中未配置 {engine.provider} 的密钥")
        return

    print(f"  [{engine_id}] 调用中...")
    t0 = time.monotonic()
    try:
        result = await asyncio.wait_for(
            engine.recognize(wav_bytes, pcm_bytes, 16000, provider_keys),
            timeout=60.0,
        )
        duration = time.monotonic() - t0

        if result.error:
            print(f"  [{engine_id}] ERROR ({duration:.1f}s): {result.error}")
        else:
            print(f"  [{engine_id}] OK ({duration:.1f}s): {result.text}")
            if reference and result.text:
                cer = calculate_cer(reference, result.text)
                if cer is not None:
                    print(f"  [{engine_id}] CER: {cer * 100:.1f}%")
    except asyncio.TimeoutError:
        print(f"  [{engine_id}] TIMEOUT (60s)")
    except Exception as e:
        duration = time.monotonic() - t0
        print(f"  [{engine_id}] EXCEPTION ({duration:.1f}s): {e}")


async def main():
    parser = argparse.ArgumentParser(description="ASR 服务开发测试")
    parser.add_argument("audio_file", help="音频文件路径 (wav/mp3/webm 等)")
    parser.add_argument("--engines", help="逗号分隔的服务 ID，不指定则跑所有已配置的", default="")
    parser.add_argument("--reference", help="参考文本，用于计算 CER", default="")
    args = parser.parse_args()

    # Read audio file
    audio_path = Path(args.audio_file)
    if not audio_path.exists():
        print(f"文件不存在: {audio_path}")
        sys.exit(1)

    audio_bytes = audio_path.read_bytes()
    print(f"音频文件: {audio_path} ({len(audio_bytes)} bytes)")

    # Convert
    print("转换音频格式...")
    wav_bytes, pcm_bytes = convert_to_pcm16k(audio_bytes)
    print(f"转换完成: WAV {len(wav_bytes)} bytes, PCM {len(pcm_bytes)} bytes")

    # Keys
    keys = get_env_keys()
    configured_providers = list(keys.keys())
    print(f"已配置的供应商: {configured_providers if configured_providers else '(无，请配置 .env)'}")

    if not configured_providers:
        print("\n请复制 .env.example 为 .env 并填写至少一家供应商的密钥")
        sys.exit(1)

    # Determine which engines to test
    if args.engines:
        engine_ids = [e.strip() for e in args.engines.split(",")]
    else:
        # All engines whose provider is configured
        engine_ids = [
            eid for eid, engine in ENGINE_REGISTRY.items()
            if engine.provider in keys
        ]

    print(f"测试服务: {engine_ids}")
    if args.reference:
        print(f"参考文本: {args.reference}")
    print()

    # Run all engines concurrently
    tasks = [
        test_engine(eid, wav_bytes, pcm_bytes, keys, args.reference)
        for eid in engine_ids
    ]
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
