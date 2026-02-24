"""Voice package - STT and TTS integration."""

__all__ = ["DeepgramSTT", "ElevenLabsTTS"]


def __getattr__(name: str):
    """Lazy import to avoid import failures when SDKs aren't perfectly configured."""
    if name == "DeepgramSTT":
        from .deepgram_stt import DeepgramSTT
        return DeepgramSTT
    if name == "ElevenLabsTTS":
        from .elevenlabs_tts import ElevenLabsTTS
        return ElevenLabsTTS
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
