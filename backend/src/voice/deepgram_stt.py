"""
Deepgram Speech-to-Text (STT) Integration.
Provides streaming transcription using Deepgram Nova-2 model.
"""
import asyncio
import json
from typing import AsyncGenerator, Callable, Awaitable

from deepgram import (
    DeepgramClient,
    DeepgramClientOptions,
    LiveTranscriptionEvents,
    LiveOptions,
)

from src.config import settings
from src.observability import get_logger


logger = get_logger(__name__)


class DeepgramSTT:
    """
    Streaming STT client using Deepgram Nova-2.
    
    Provides real-time audio transcription with:
    - Interim (partial) and final transcript results
    - Endpointing detection (300ms silence = end of utterance)
    - Banking keyword boosting for improved accuracy
    - Auto-reconnect on connection failures
    """
    
    def __init__(self):
        self.client = DeepgramClient(settings.deepgram_api_key)
        self.connection = None
        self._transcript_queue: asyncio.Queue | None = None
        self._is_connected = False
    
    async def start_stream(
        self,
        on_transcript: Callable[[str, bool], Awaitable[None]] | None = None,
    ) -> asyncio.Queue:
        """
        Start a streaming transcription session.
        
        Args:
            on_transcript: Optional async callback(text, is_final) for each transcript.
                          If not provided, transcripts are placed in the returned queue.
        
        Returns:
            Queue that receives (transcript_text, is_final) tuples
        """
        self._transcript_queue = asyncio.Queue()
        
        # Create live transcription connection
        self.connection = self.client.listen.asynclive.v("1")
        
        # Register event handlers
        @self.connection.on(LiveTranscriptionEvents.Open)
        async def on_open(client, open_event, **kwargs):
            logger.info("🎤 Deepgram STT connection opened")
            self._is_connected = True
        
        @self.connection.on(LiveTranscriptionEvents.Transcript)
        async def on_message(client, result, **kwargs):
            try:
                transcript = result.channel.alternatives[0].transcript
                is_final = result.is_final
                
                if not transcript.strip():
                    return
                
                if on_transcript:
                    await on_transcript(transcript, is_final)
                
                # Always put in queue for consumers
                await self._transcript_queue.put((transcript, is_final))
                
                log_prefix = "📝 FINAL" if is_final else "📝 interim"
                logger.debug(f"{log_prefix}: {transcript}")
                    
            except Exception as e:
                logger.error(f"Error processing Deepgram transcript: {e}")
        
        @self.connection.on(LiveTranscriptionEvents.Error)
        async def on_error(client, error, **kwargs):
            logger.error(f"Deepgram STT error: {error}")
        
        @self.connection.on(LiveTranscriptionEvents.Close)
        async def on_close(client, close_event, **kwargs):
            logger.info("🎤 Deepgram STT connection closed")
            self._is_connected = False
        
        # Configure live transcription options
        options = LiveOptions(
            model=settings.deepgram_model,
            language="en-US",
            punctuate=True,
            smart_format=True,
            interim_results=True,
            endpointing=300,          # 300ms silence = utterance end
            utterance_end_ms=1000,    # 1s silence = definite end
            encoding="linear16",
            sample_rate=16000,
            channels=1,
            # Boost banking-specific terms
            keywords=[
                "Bank ABC:2",
                "account:2",
                "balance:2",
                "routing number:3",
                "customer ID:3",
            ],
        )
        
        # Start the connection
        if await self.connection.start(options) is False:
            logger.error("Failed to start Deepgram STT connection")
            raise ConnectionError("Failed to connect to Deepgram STT")
        
        logger.info("✅ Deepgram STT streaming started")
        return self._transcript_queue
    
    async def send_audio(self, audio_bytes: bytes):
        """
        Send audio data to Deepgram for transcription.
        
        Args:
            audio_bytes: Raw PCM audio data (16kHz, 16-bit, mono)
        """
        if self.connection and self._is_connected:
            await self.connection.send(audio_bytes)
    
    async def close(self):
        """Close the Deepgram streaming connection."""
        if self.connection:
            try:
                await self.connection.finish()
            except Exception as e:
                logger.warning(f"Error closing Deepgram connection: {e}")
            finally:
                self.connection = None
                self._is_connected = False
                logger.info("Deepgram STT connection cleaned up")
    
    @property
    def is_connected(self) -> bool:
        """Check if the STT stream is active."""
        return self._is_connected
