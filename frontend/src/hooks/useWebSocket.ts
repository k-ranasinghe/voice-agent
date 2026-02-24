import { useRef, useCallback, useState } from "react";
import { useCallStore } from "../stores/callStore";

type MessageHandler = (data: Record<string, unknown>) => void;

const WS_URL = import.meta.env.VITE_WS_URL || "ws://localhost:8000";
const RECONNECT_DELAYS = [3000, 6000, 12000]; // Exponential backoff

export function useWebSocket() {
    const wsRef = useRef<WebSocket | null>(null);
    const handlersRef = useRef<Map<string, MessageHandler>>(new Map());
    const reconnectAttemptRef = useRef(0);
    const [isConnected, setIsConnected] = useState(false);

    const { setCallStatus, setSessionId, setAgentStatus, addMessage, updateLastInterim, setStateUpdate } =
        useCallStore();

    const processMessage = useCallback(
        (event: MessageEvent) => {
            try {
                const data = JSON.parse(event.data);
                const type = data.type as string;

                switch (type) {
                    case "session":
                        setSessionId(data.session_id);
                        setCallStatus("active");
                        break;

                    case "transcript": {
                        if (data.is_final === false && data.speaker === "user") {
                            updateLastInterim(data.text);
                        } else {
                            addMessage({
                                id: crypto.randomUUID(),
                                speaker: data.speaker,
                                text: data.text,
                                isFinal: data.is_final ?? true,
                                timestamp: data.timestamp || new Date().toISOString(),
                            });
                        }
                        break;
                    }

                    case "status":
                        setAgentStatus(data.status);
                        break;

                    case "state_update":
                        setStateUpdate({
                            intent: data.intent,
                            authenticated: data.authenticated,
                            flowStage: data.flow_stage,
                            escalationRequested: data.escalation_requested,
                        });
                        break;
                }

                // Call custom handler if registered
                const handler = handlersRef.current.get(type);
                if (handler) handler(data);
            } catch (e) {
                console.error("Failed to parse WS message:", e);
            }
        },
        [setSessionId, setCallStatus, setAgentStatus, addMessage, updateLastInterim, setStateUpdate]
    );

    const connect = useCallback(
        (mode: "text" | "voice" = "voice") => {
            const path = mode === "voice" ? "/ws/voice" : "/ws";
            const url = `${WS_URL}${path}`;

            setCallStatus("connecting");

            const ws = new WebSocket(url);
            wsRef.current = ws;

            ws.onopen = () => {
                console.log(`[WS] Connected to ${url}`);
                setIsConnected(true);
                reconnectAttemptRef.current = 0;

                if (mode === "text") {
                    setCallStatus("active");
                    setSessionId(crypto.randomUUID());
                }
            };

            ws.onmessage = processMessage;

            ws.onclose = (e) => {
                console.log(`[WS] Disconnected: code=${e.code}`);
                setIsConnected(false);

                // Auto-reconnect if not a clean close
                if (e.code !== 1000) {
                    const attempt = reconnectAttemptRef.current;
                    if (attempt < RECONNECT_DELAYS.length) {
                        const delay = RECONNECT_DELAYS[attempt];
                        console.log(`[WS] Reconnecting in ${delay}ms (attempt ${attempt + 1})`);
                        reconnectAttemptRef.current++;
                        setTimeout(() => connect(mode), delay);
                    } else {
                        setCallStatus("ended");
                    }
                } else {
                    setCallStatus("ended");
                }
            };

            ws.onerror = (e) => {
                console.error("[WS] Error:", e);
            };
        },
        [processMessage, setCallStatus, setSessionId, setIsConnected]
    );

    const disconnect = useCallback(() => {
        if (wsRef.current) {
            // Send stop message before closing
            if (wsRef.current.readyState === WebSocket.OPEN) {
                wsRef.current.send(JSON.stringify({ type: "stop" }));
            }
            wsRef.current.close(1000, "User disconnected");
            wsRef.current = null;
        }
        setIsConnected(false);
        setCallStatus("ended");
    }, [setCallStatus, setIsConnected]);

    const sendText = useCallback((text: string) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: "text", content: text }));
        }
    }, []);

    const sendAudio = useCallback((audioData: ArrayBuffer) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(audioData);
        }
    }, []);

    const on = useCallback((eventType: string, handler: MessageHandler) => {
        handlersRef.current.set(eventType, handler);
    }, []);

    return {
        connect,
        disconnect,
        sendText,
        sendAudio,
        on,
        isConnected,
        ws: wsRef,
    };
}
