import asyncio
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv

# Load .env once at startup, before any other backend module reads os.getenv
load_dotenv(Path(__file__).parent.parent / ".env")

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.audio_utils import MAX_FILE_SIZE, convert_to_pcm16k
from backend.cer_utils import calculate_cer
from backend.engines import ENGINE_REGISTRY
from backend.key_crypto import decrypt_keys, encrypt_keys
from backend.rate_limit import rate_limiter

app = FastAPI(title="ASR Compare")

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"


@app.post("/api/merge-keys")
async def api_merge_keys(body: dict):
    """Merge new plaintext keys with existing encrypted keys, return new ciphertext."""
    new_keys = body.get("new_keys", {})
    existing_encrypted = body.get("existing_encrypted", "")

    # Decrypt existing keys (if any)
    merged = {}
    if existing_encrypted:
        try:
            merged = decrypt_keys(existing_encrypted)
        except ValueError:
            pass  # Old keys unrecoverable, start fresh

    # Overlay new keys per provider
    for provider, pkeys in new_keys.items():
        if pkeys:
            merged[provider] = pkeys

    encrypted = encrypt_keys(merged)

    # Return list of configured providers for frontend checkbox logic
    providers = [p for p, k in merged.items() if k]

    return {"encrypted": encrypted, "providers": providers}


@app.post("/api/recognize")
async def recognize(
    audio: UploadFile = File(...),
    config: str = Form(...),
):
    cfg = json.loads(config)
    engines_requested = cfg.get("engines", [])
    encrypted_keys = cfg.get("encrypted_keys", "")
    reference_text = cfg.get("reference_text", "")

    # Decrypt keys
    if not encrypted_keys:
        return JSONResponse(status_code=400, content={"error": "未提供密钥"})
    try:
        keys = decrypt_keys(encrypted_keys)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})

    # Rate limit check
    rate_error = rate_limiter.check(keys)
    if rate_error:
        return JSONResponse(status_code=429, content={"error": rate_error})

    # Read and validate audio
    audio_bytes = await audio.read()
    if len(audio_bytes) > MAX_FILE_SIZE:
        return JSONResponse(
            status_code=400,
            content={"error": f"文件大小超过限制 ({MAX_FILE_SIZE // 1024 // 1024}MB)"},
        )

    # Convert audio once
    try:
        wav_bytes, pcm_bytes = await asyncio.to_thread(convert_to_pcm16k, audio_bytes)
    except ValueError as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception:
        return JSONResponse(status_code=400, content={"error": "无法解析音频文件，请检查格式"})

    # Build engine tasks
    async def call_engine(engine_id: str):
        engine = ENGINE_REGISTRY.get(engine_id)
        if not engine:
            return engine_id, {"text": None, "duration_ms": 0, "cer": None, "error": f"未知引擎: {engine_id}"}

        provider_keys = keys.get(engine.provider)
        if not provider_keys:
            return engine_id, {"text": None, "duration_ms": 0, "cer": None, "error": "未配置 API 密钥"}

        t0 = time.monotonic()
        print(f"[{engine_id}] Starting recognition, audio: WAV={len(wav_bytes)}B PCM={len(pcm_bytes)}B")
        try:
            result = await asyncio.wait_for(
                engine.recognize(wav_bytes, pcm_bytes, 16000, provider_keys),
                timeout=60.0,
            )
            duration_ms = int((time.monotonic() - t0) * 1000)
            cer_val = None
            if reference_text and result.text:
                cer_val = calculate_cer(reference_text, result.text)
            return engine_id, {
                "text": result.text,
                "duration_ms": duration_ms,
                "cer": cer_val,
                "error": result.error,
            }
        except asyncio.TimeoutError:
            print(f"[{engine_id}] TIMEOUT after 60s")
            return engine_id, {"text": None, "duration_ms": 60000, "cer": None, "error": "超时 (60秒)"}
        except Exception as e:
            duration_ms = int((time.monotonic() - t0) * 1000)
            print(f"[{engine_id}] ERROR ({duration_ms}ms): {type(e).__name__}: {e}")
            return engine_id, {"text": None, "duration_ms": duration_ms, "cer": None, "error": str(e)}

    print(f"[recognize] engines_requested={engines_requested}")
    print(f"[recognize] keys providers={list(keys.keys())}")

    # SSE stream: yield results as each engine completes
    async def event_stream():
        tasks = {asyncio.create_task(call_engine(eid)): eid for eid in engines_requested}

        for coro in asyncio.as_completed(tasks):
            engine_id, result = await coro
            event_data = json.dumps({"engine_id": engine_id, "result": result}, ensure_ascii=False)
            yield f"data: {event_data}\n\n"

        # Signal completion
        yield "data: {\"done\": true}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/cer")
async def compute_cer(body: dict):
    """Calculate CER for multiple hypotheses against a reference text."""
    reference = body.get("reference_text", "")
    hypotheses = body.get("hypotheses", {})
    results = {}
    for engine_id, text in hypotheses.items():
        if reference and text:
            results[engine_id] = calculate_cer(reference, text)
        else:
            results[engine_id] = None
    return {"cer": results}


@app.get("/api/engines")
async def list_engines():
    """Return available engines and their provider requirements."""
    return {
        "engines": [
            {
                "id": e.engine_id,
                "name": e.display_name,
                "provider": e.provider,
            }
            for e in ENGINE_REGISTRY.values()
        ]
    }


# Mount frontend static files (must be last)
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    # Run from project root: uv run python -m backend.main
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000)
