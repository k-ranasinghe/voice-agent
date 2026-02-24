"""
WebSocket Handler for Text-Based Agent Testing.
Provides WebSocket endpoint for real-time conversation without voice (Phase 4).
Voice streaming will be added in Phase 6.
"""
import uuid
import asyncio
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


class ConnectionManager:
    """Manages active WebSocket connections."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
    
    async def connect(self, session_id: str, websocket: WebSocket):
        """Accept and store WebSocket connection."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
        logger.info(f"WebSocket connected: {session_id}")
    
    def disconnect(self, session_id: str):
        """Remove WebSocket connection."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
            logger.info(f"WebSocket disconnected: {session_id}")
    
    async def send_message(self, session_id: str, message: dict):
        """Send JSON message to client."""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            await websocket.send_json(message)


manager = ConnectionManager()


async def create_call_session(customer_id: str | None = None) -> str:
    """
    Create a new call session in the database.
    
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
        logger.info(f"Created call session: {session_id}")
        
        return session_id


async def handle_websocket_text(websocket: WebSocket):
    """
    Handle text-based WebSocket connection for agent testing.
    
    Message Protocol (JSON):
    
    Client → Server:
    {
        "type": "text",
        "content": "User message here"
    }
    
    Server → Client:
    {
        "type": "transcript",
        "speaker": "user" | "agent",
        "text": "Message content",
        "timestamp": "ISO datetime"
    }
    
    {
        "type": "status",
        "status": "idle" | "thinking" | "error"
    }
    
    {
        "type": "state_update",
        "intent": "card_atm",
        "authenticated": true,
        ...other state fields
    }
    """
    
    # Create session
    session_id = await create_call_session()
    start_time = datetime.utcnow()
    
    # Connect WebSocket
    await manager.connect(session_id, websocket)
    
    # Initialize agent state
    initial_state: AgentState = {
        "messages": [],
        "customer_id": None,
        "authenticated": False,
        "authentication_method": None,
        "verification_attempts": 0,
        "session_id": session_id,
        "intent": None,
        "intent_confidence": None,
        "flow_stage": None,
        "needs_user_input": False,
        "resume_node": None,
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
    
    # Get compiled graph
    agent_graph = get_agent_graph()
    
    # Configuration for graph invocation
    config = {
        "configurable": {
            "thread_id": session_id  # For checkpointing
        }
    }
    
    try:
        # Send welcome message
        await manager.send_message(session_id, {
            "type": "transcript",
            "speaker": "agent",
            "text": "Hello! I'm Bank ABC's virtual assistant. How can I help you today?",
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Main conversation loop
        while True:
            # Wait for user message
            data = await websocket.receive_json()
            
            if data.get("type") == "text":
                user_message = data.get("content", "")
                
                if not user_message.strip():
                    continue
                
                logger.info(f"Received message: {user_message[:100]}...")
                
                # Log user message
                await log_transcript(session_id, "user", user_message)
                
                # Note: frontend adds the user message locally in handleSendText,
                # so we don't echo it back here to avoid duplicates.
                
                # Set thinking status
                await manager.send_message(session_id, {
                    "type": "status",
                    "status": "thinking"
                })
                
                # Add user message to state
                initial_state["messages"].append(HumanMessage(content=user_message))
                initial_state["turn_count"] += 1
                
                # Reset needs_user_input so the graph can proceed
                # Keep resume_node so intent_router knows where to route
                initial_state["needs_user_input"] = False
                
                # Invoke agent graph
                try:
                    result = await agent_graph.ainvoke(initial_state, config)
                    
                    # After invocation, consume resume_node so it doesn't
                    # persist to the next turn (unless the graph sets it again)
                    # The graph result will contain the new state
                    initial_state = dict(result)
                    
                    # Extract agent response from last message
                    agent_messages = [msg for msg in result["messages"] if isinstance(msg, AIMessage)]
                    
                    if agent_messages:
                        agent_response = agent_messages[-1].content
                        
                        # Log agent response
                        await log_transcript(session_id, "agent", agent_response)
                        
                        # Send agent response
                        await manager.send_message(session_id, {
                            "type": "transcript",
                            "speaker": "agent",
                            "text": agent_response,
                            "timestamp": datetime.utcnow().isoformat()
                        })
                    
                    # Update state for next turn
                    initial_state = result
                    
                    # Send state update
                    await manager.send_message(session_id, {
                        "type": "state_update",
                        "intent": result.get("intent"),
                        "authenticated": result.get("authenticated", False),
                        "flow_stage": result.get("flow_stage"),
                        "escalation_requested": result.get("escalation_requested", False),
                    })
                    
                    # Update database session
                    await update_session(
                        session_id=session_id,
                        customer_id=result.get("customer_id"),
                        intent=result.get("intent"),
                        authenticated=result.get("authenticated", False),
                        escalated=result.get("escalation_requested", False),
                        escalation_reason=result.get("escalation_reason"),
                    )
                    
                    # Set idle status
                    await manager.send_message(session_id, {
                        "type": "status",
                        "status": "idle"
                    })
                    
                    # Check if conversation ended
                    if result.get("escalation_requested"):
                        logger.info(f"Conversation escalated, ending: {session_id}")
                        break
                    
                    # Reset flow state for next turn so the graph can
                    # be re-invoked fresh for the next user message
                    if result.get("flow_stage") == "complete":
                        initial_state["flow_stage"] = None
                        initial_state["intent"] = None
                        initial_state["intent_confidence"] = None
                        initial_state["resume_node"] = None
                
                except Exception as e:
                    logger.error(f"Agent error: {e}", exc_info=True)
                    
                    await manager.send_message(session_id, {
                        "type": "transcript",
                        "speaker": "agent",
                        "text": "I apologize, but I'm experiencing technical difficulties. Please try again.",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                    await manager.send_message(session_id, {
                        "type": "status",
                        "status": "error"
                    })
    
    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {session_id}")
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    
    finally:
        # Disconnect and cleanup
        manager.disconnect(session_id)
        
        # Calculate duration
        duration = int((datetime.utcnow() - start_time).total_seconds())
        
        # Close session
        await close_session(session_id, duration)
        
        logger.info(f"Session closed: {session_id} | Duration: {duration}s")
