import io
import resource
import subprocess

from pydub import AudioSegment


MAX_DURATION_SECONDS = 75
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
FFMPEG_TIMEOUT_SECONDS = 30
FFMPEG_MAX_DATA_BYTES = 1024 * 1024 * 1024  # 1GB data segment limit


def _limit_subprocess_resources():
    """Called in ffmpeg child process to cap heap/data memory usage."""
    resource.setrlimit(resource.RLIMIT_DATA, (FFMPEG_MAX_DATA_BYTES, FFMPEG_MAX_DATA_BYTES))


# Patch pydub's subprocess call to inject timeout and memory limits.
_original_popen = subprocess.Popen


class _SafePopen(_original_popen):
    """Popen wrapper that enforces timeout and memory limits on ffmpeg."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("preexec_fn", _limit_subprocess_resources)
        super().__init__(*args, **kwargs)

    def communicate(self, input=None, timeout=None):
        if timeout is None:
            timeout = FFMPEG_TIMEOUT_SECONDS
        return super().communicate(input=input, timeout=timeout)


def convert_to_pcm16k(audio_bytes: bytes) -> tuple[bytes, bytes]:
    """
    Convert any audio format to 16kHz 16-bit mono PCM.

    Returns:
        (wav_bytes, raw_pcm_bytes)
        wav_bytes: Complete WAV file bytes (with header).
        raw_pcm_bytes: Raw PCM data without WAV header.
    """
    # Use patched Popen for this conversion
    subprocess.Popen = _SafePopen
    try:
        audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    except subprocess.TimeoutExpired:
        raise ValueError("音频解码超时，文件可能已损坏或格式不支持")
    except MemoryError:
        raise ValueError("音频解码占用内存过大")
    finally:
        subprocess.Popen = _original_popen

    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)

    duration_sec = len(audio) / 1000.0
    if duration_sec > MAX_DURATION_SECONDS:
        raise ValueError(f"音频时长 {duration_sec:.1f}s 超过限制 ({MAX_DURATION_SECONDS}s)")

    # Also use patched Popen for export
    subprocess.Popen = _SafePopen
    try:
        wav_buf = io.BytesIO()
        audio.export(wav_buf, format="wav")
    except subprocess.TimeoutExpired:
        raise ValueError("音频转码超时")
    finally:
        subprocess.Popen = _original_popen

    wav_bytes = wav_buf.getvalue()
    raw_pcm = audio.raw_data

    return wav_bytes, raw_pcm


