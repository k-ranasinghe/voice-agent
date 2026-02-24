"""
ElevenLabs Text-to-Speech (TTS) Integration.
Provides streaming audio generation using ElevenLabs Turbo v2 model.
"""
import asyncio
from typing import AsyncGenerator

from elevenlabs.client import AsyncElevenLabs

from src.config import settings
from src.observability import get_logger


logger = get_logger(__name__)


class ElevenLabsTTS:
    """
    Streaming TTS client using ElevenLabs.
    
    Provides real-time text-to-speech with:
    - Chunk-based audio streaming (<200ms first chunk)
    - Configurable voice and model selection
    - Stability/similarity tuning for natural prosody
    """
    
    def __init__(self):
        self.client = AsyncElevenLabs(api_key=settings.elevenlabs_api_key)
        self.voice_id = settings.elevenlabs_voice_id
        self.model_id = settings.elevenlabs_model
    
    async def stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Stream audio generation for the given text.
        
        Yields audio chunks as they become available from ElevenLabs.
        Audio format: MP3 by default (browser-compatible).
        
        Args:
            text: Text to convert to speech
            
        Yields:
            bytes: Audio data chunks
        """
        if not text or not text.strip():
            logger.warning("Empty text provided to TTS, skipping")
            return
        
        logger.info(f"🔊 TTS generating: {text[:80]}...")
        
        try:
            # Use streaming generation for low-latency audio
            audio_stream = await self.client.text_to_speech.convert(
                text=text,
                voice_id=self.voice_id,
                model_id=self.model_id,
                output_format="mp3_44100_128",
                voice_settings={
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                    "style": 0.0,
                    "use_speaker_boost": True,
                },
            )
            
            # audio_stream is an iterator of bytes
            # Yield chunks to allow streaming to the client
            if isinstance(audio_stream, bytes):
                # Non-streaming response — yield as single chunk
                yield audio_stream
            else:
                # Streaming response — yield each chunk
                async for chunk in audio_stream:
                    if chunk:
                        yield chunk
            
            logger.debug(f"🔊 TTS complete for: {text[:40]}...")
            
        except Exception as e:
            logger.error(f"ElevenLabs TTS error: {e}", exc_info=True)
            raise
    
    async def generate(self, text: str) -> bytes:
        """
        Generate complete audio for the given text (non-streaming).
        
        Args:
            text: Text to convert to speech
            
        Returns:
            Complete audio data as bytes
        """
        chunks = []
        async for chunk in self.stream(text):
            chunks.append(chunk)
        return b"".join(chunks)
