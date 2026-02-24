"""
Voice WebSocket Handler.
Implements the 4-task parallel audio pipeline for real-time voice conversations.

Pipeline Architecture:
    Browser → [audio_receiver] → Deepgram → [stt_worker] → Agent → [agent_worker] → ElevenLabs → [tts_worker] → Browser

Each task runs concurrently via asyncio, communicating through asyncio.Queues.
"""
import uuid
import asyncio
import base64
import json
from datetime import datetime
from typing import Dict

from fastapi import WebSocket, WebSocketDisconnect
from langchain_core.messages import HumanMessage, AIMessage

from src.agents import get_agent_graph
from src.agents.state import AgentState
from src.observability import get_logger, log_transcript, update_session, close_session
from src.database.connection import async_session
from src.database.models import CallSession


logger = get_logger(__name__)


class VoiceConnectionManager:
    """Manages active voice WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, session_id: str, websocket: WebSocket):
        """Accept and store WebSocket connection."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"Voice WebSocket connected: {session_id}")
    
    def disconnect(self, session_id: str):
        """Remove WebSocket connection."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"Voice WebSocket disconnected: {session_id}")
    
    async def send_json(self, session_id: str, message: dict):
        """Send JSON message to client."""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            await websocket.send_json(message)
    
    async def send_bytes(self, session_id: str, data: bytes):
        """Send binary data (audio) to client."""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            await websocket.send_bytes(data)


voice_manager = VoiceConnectionManager()


async def create_voice_session(customer_id: str | None = None) -> str:
    """
    Create a new call session in the database for voice calls.
    
    Returns:
        Session UUID
    """
    async with async_session() as session:
        call_session = CallSession(
            customer_id=customer_id,
            intent=None,
            authenticated=False,
            escalated=False,
            started_at=datetime.utcnow(),
        )
        
        session.add(call_session)
        await session.commit()
        await session.refresh(call_session)
        
        session_id = str(call_session.session_id)
        logger.info(f"Created voice call session: {session_id}")
        
        return session_id


async def handle_voice_websocket(websocket: WebSocket):
    """
    Handle voice WebSocket connection with 4-task parallel pipeline.
    
    Message Protocol:
    
    Client → Server:
        Binary frames: Raw PCM audio (16kHz, 16-bit, mono)
        JSON frames:
            {"type": "start"}    - Begin voice session
            {"type": "stop"}     - End voice session
    
    Server → Client:
        JSON frames:
            {"type": "transcript", "speaker": "user"|"agent", "text": "...", "is_final": true|false}
            {"type": "status", "status": "idle"|"listening"|"thinking"|"speaking"}
            {"type": "state_update", "intent": "...", "authenticated": true|false, ...}
            {"type": "audio", "data": "<base64 mp3>"}  - Agent speech audio chunk
            {"type": "audio_end"}                       - Signals end of audio stream
            {"type": "session", "session_id": "..."}    - Session established
            {"type": "error", "message": "..."}         - Error notification
    """
    
    # Create session
    session_id = await create_voice_session()
    start_time = datetime.utcnow()
    
    # Connect WebSocket
    await voice_manager.connect(session_id, websocket)
    
    # Initialize voice components (lazy import to avoid startup crashes)
    from src.voice.deepgram_stt import DeepgramSTT
    from src.voice.elevenlabs_tts import ElevenLabsTTS
    stt = DeepgramSTT()
    tts = ElevenLabsTTS()
    
    # Inter-task communication queues
    stt_queue: asyncio.Queue = asyncio.Queue()          # STT → agent_worker
    tts_queue: asyncio.Queue = asyncio.Queue()          # agent_worker → tts_worker
    audio_in_queue: asyncio.Queue = asyncio.Queue()     # audio_receiver → stt_worker
    
    # Shared agent state
    agent_state: AgentState = {
        "messages": [],
        "customer_id": None,
        "authenticated": False,
        "authentication_method": None,
        "verification_attempts": 0,
        "session_id": session_id,
        "intent": None,
        "intent_confidence": None,
        "flow_stage": None,
        "escalation_requested": False,
        "escalation_reason": None,
        "last_tool_output": None,
        "account_balance": None,
        "recent_transactions": None,
        "card_details": None,
        "pii_detected": [],
        "suspicious_activity": False,
        "critical_actions_taken": [],
        "turn_count": 0,
        "start_time": start_time.timestamp(),
    }
    
    # State lock for thread-safe updates
    state_lock = asyncio.Lock()
    
    # Shutdown event
    shutdown_event = asyncio.Event()
    
    # ==================== TASK 1: Audio Receiver ====================
    
    async def audio_receiver():
        """
        Receives audio from browser WebSocket and queues for STT.
        Also handles JSON control messages.
        """
        try:
            while not shutdown_event.is_set():
                try:
                    message = await asyncio.wait_for(
                        websocket.receive(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                if message["type"] == "websocket.disconnect":
                    logger.info(f"Client disconnected: {session_id}")
                    shutdown_event.set()
                    break
                
                if "bytes" in message and message["bytes"]:
                    # Binary frame → raw PCM audio
                    await audio_in_queue.put(message["bytes"])
                
                elif "text" in message and message["text"]:
                    # JSON control message
                    try:
                        data = json.loads(message["text"])
                        msg_type = data.get("type", "")
                        
                        if msg_type == "stop":
                            logger.info(f"Client requested stop: {session_id}")
                            shutdown_event.set()
                            break
                    except json.JSONDecodeError:
                        logger.warning("Received invalid JSON from client")
                        
        except WebSocketDisconnect:
            logger.info(f"WebSocket disconnected in audio_receiver: {session_id}")
            shutdown_event.set()
        except Exception as e:
            logger.error(f"Audio receiver error: {e}", exc_info=True)
            shutdown_event.set()
    
    # ==================== TASK 2: STT Worker ====================
    
    async def stt_worker():
        """
        Streams audio to Deepgram and forwards final transcripts to agent queue.
        Sends interim transcripts to UI for real-time feedback.
        """
        try:
            # Define transcript callback
            async def on_transcript(text: str, is_final: bool):
                # Send transcript to frontend (both interim and final)
                await voice_manager.send_json(session_id, {
                    "type": "transcript",
                    "speaker": "user",
                    "text": text,
                    "is_final": is_final,
                    "timestamp": datetime.utcnow().isoformat(),
                })
                
                # Only send final transcripts to agent
                if is_final:
                    await log_transcript(session_id, "user", text)
                    await stt_queue.put(text)
            
            # Start STT stream
            await stt.start_stream(on_transcript=on_transcript)
            
            # Set listening status
            await voice_manager.send_json(session_id, {
                "type": "status",
                "status": "listening"
            })
            
            # Forward audio to Deepgram
            while not shutdown_event.is_set():
                try:
                    audio_bytes = await asyncio.wait_for(
                        audio_in_queue.get(),
                        timeout=1.0
                    )
                    await stt.send_audio(audio_bytes)
                except asyncio.TimeoutError:
                    continue
                    
        except Exception as e:
            logger.error(f"STT worker error: {e}", exc_info=True)
        finally:
            await stt.close()
    
    # ==================== TASK 3: Agent Worker ====================
    
    async def agent_worker():
        """
        Processes user transcripts through LangGraph agent.
        Forwards agent responses to TTS queue.
        """
        nonlocal agent_state
        
        # Get compiled graph
        agent_graph = get_agent_graph()
        config = {
            "configurable": {
                "thread_id": session_id
            }
        }
        
        # Send initial greeting via TTS
        greeting = "Hello! I'm Bank ABC's virtual assistant. How can I help you today?"
        await tts_queue.put(greeting)
        await log_transcript(session_id, "agent", greeting)
        
        try:
            while not shutdown_event.is_set():
                try:
                    # Wait for final transcript from STT
                    user_text = await asyncio.wait_for(
                        stt_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                logger.info(f"Agent processing: {user_text[:100]}...")
                
                # Set thinking status
                await voice_manager.send_json(session_id, {
                    "type": "status",
                    "status": "thinking"
                })
                
                # Update state with user message
                async with state_lock:
                    agent_state["messages"].append(HumanMessage(content=user_text))
                    agent_state["turn_count"] += 1
                
                # Invoke LangGraph agent
                try:
                    result = await agent_graph.ainvoke(agent_state, config)
                    
                    # Extract agent response
                    agent_messages = [
                        msg for msg in result["messages"]
                        if isinstance(msg, AIMessage)
                    ]
                    
                    if agent_messages:
                        agent_response = agent_messages[-1].content
                        
                        # Log agent response
                        await log_transcript(session_id, "agent", agent_response)
                        
                        # Send text transcript to UI
                        await voice_manager.send_json(session_id, {
                            "type": "transcript",
                            "speaker": "agent",
                            "text": agent_response,
                            "is_final": True,
                            "timestamp": datetime.utcnow().isoformat(),
                        })
                        
                        # Queue for TTS
                        await tts_queue.put(agent_response)
                    
                    # Update shared state
                    async with state_lock:
                        agent_state = result
                    
                    # Send state update to UI
                    await voice_manager.send_json(session_id, {
                        "type": "state_update",
                        "intent": result.get("intent"),
                        "authenticated": result.get("authenticated", False),
                        "flow_stage": result.get("flow_stage"),
                        "escalation_requested": result.get("escalation_requested", False),
                    })
                    
                    # Update database
                    await update_session(
                        session_id=session_id,
                        customer_id=result.get("customer_id"),
                        intent=result.get("intent"),
                        authenticated=result.get("authenticated", False),
                        escalated=result.get("escalation_requested", False),
                        escalation_reason=result.get("escalation_reason"),
                    )
                    
                    # Check if conversation ended
                    if result.get("escalation_requested") or result.get("flow_stage") == "complete":
                        logger.info(f"Voice conversation ended: {session_id}")
                        # Let TTS finish before shutting down
                        await asyncio.sleep(2)
                        shutdown_event.set()
                        break
                
                except Exception as e:
                    logger.error(f"Agent error: {e}", exc_info=True)
                    
                    error_msg = "I apologize, but I'm experiencing technical difficulties. Could you please repeat that?"
                    await tts_queue.put(error_msg)
                    
                    await voice_manager.send_json(session_id, {
                        "type": "transcript",
                        "speaker": "agent",
                        "text": error_msg,
                        "is_final": True,
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                    
        except Exception as e:
            logger.error(f"Agent worker error: {e}", exc_info=True)
    
    # ==================== TASK 4: TTS Worker ====================
    
    async def tts_worker():
        """
        Converts agent text responses to audio using ElevenLabs.
        Streams audio chunks back to the browser.
        """
        try:
            while not shutdown_event.is_set():
                try:
                    text = await asyncio.wait_for(
                        tts_queue.get(),
                        timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Set speaking status
                await voice_manager.send_json(session_id, {
                    "type": "status",
                    "status": "speaking"
                })
                
                try:
                    # Stream TTS audio to client
                    async for audio_chunk in tts.stream(text):
                        if shutdown_event.is_set():
                            break
                        
                        # Send audio chunk as base64 JSON
                        audio_b64 = base64.b64encode(audio_chunk).decode("utf-8")
                        await voice_manager.send_json(session_id, {
                            "type": "audio",
                            "data": audio_b64,
                        })
                    
                    # Signal end of audio stream
                    await voice_manager.send_json(session_id, {
                        "type": "audio_end"
                    })
                    
                except Exception as e:
                    logger.error(f"TTS streaming error: {e}", exc_info=True)
                
                # Return to listening status
                if not shutdown_event.is_set():
                    await voice_manager.send_json(session_id, {
                        "type": "status",
                        "status": "listening"
                    })
                    
        except Exception as e:
            logger.error(f"TTS worker error: {e}", exc_info=True)
    
    # ==================== Main Orchestration ====================
    
    try:
        # Send session info to client
        await voice_manager.send_json(session_id, {
            "type": "session",
            "session_id": session_id,
        })
        
        # Run all 4 tasks concurrently
        tasks = [
            asyncio.create_task(audio_receiver(), name="audio_receiver"),
            asyncio.create_task(stt_worker(), name="stt_worker"),
            asyncio.create_task(agent_worker(), name="agent_worker"),
            asyncio.create_task(tts_worker(), name="tts_worker"),
        ]
        
        # Wait for any task to signal shutdown
        done, pending = await asyncio.wait(
            tasks,
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Signal all tasks to stop
        shutdown_event.set()
        
        # Give pending tasks time to cleanup
        for task in pending:
            task.cancel()
        
        await asyncio.gather(*pending, return_exceptions=True)
        
    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {session_id}")
    except Exception as e:
        logger.error(f"Voice WebSocket error: {e}", exc_info=True)
    finally:
        # Cleanup
        voice_manager.disconnect(session_id)
        await stt.close()
        
        # Calculate duration
        duration = int((datetime.utcnow() - start_time).total_seconds())
        
        # Close session in DB
        await close_session(session_id, duration)
        
        logger.info(f"Voice session closed: {session_id} | Duration: {duration}s")
