import io
from pydub import AudioSegment


MAX_DURATION_SECONDS = 75
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB


def convert_to_pcm16k(audio_bytes: bytes) -> tuple[bytes, bytes]:
    """
    Convert any audio format to 16kHz 16-bit mono PCM.

    Returns:
        (wav_bytes, raw_pcm_bytes)
        wav_bytes: Complete WAV file bytes (with header).
        raw_pcm_bytes: Raw PCM data without WAV header.
    """
    audio = AudioSegment.from_file(io.BytesIO(audio_bytes))
    audio = audio.set_frame_rate(16000).set_channels(1).set_sample_width(2)

    duration_sec = len(audio) / 1000.0
    if duration_sec > MAX_DURATION_SECONDS:
        raise ValueError(f"音频时长 {duration_sec:.1f}s 超过限制 ({MAX_DURATION_SECONDS}s)")

    wav_buf = io.BytesIO()
    audio.export(wav_buf, format="wav")
    wav_bytes = wav_buf.getvalue()

    raw_pcm = audio.raw_data

    return wav_bytes, raw_pcm


