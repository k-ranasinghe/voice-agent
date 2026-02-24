import { useState, useCallback } from "react";
import { Phone, MessageSquare, Headphones } from "lucide-react";
import { useWebSocket } from "../../hooks/useWebSocket";
import { useAudioCapture } from "../../hooks/useAudioCapture";
import { useAudioPlayback } from "../../hooks/useAudioPlayback";
import { useCallStore } from "../../stores/callStore";
import { AudioVisualizer } from "./AudioVisualizer";
import { TranscriptDisplay } from "./TranscriptDisplay";
import { CallControls } from "./CallControls";

type Mode = "voice" | "text";

/**
 * Main call interface page.
 * Supports both voice (STT/TTS) and text (WebSocket JSON) modes.
 */
export function CallInterface() {
    const [mode, setMode] = useState<Mode>("text");
    const [textInput, setTextInput] = useState("");

    const {
        callStatus,
        agentStatus,
        messages,
        isMuted,
        volume,
        stateUpdate,
        toggleMute,
        setVolume,
        reset,
    } = useCallStore();

    const { connect, disconnect, sendText, sendAudio, on } = useWebSocket();
    const { startRecording, stopRecording, analyserNode } = useAudioCapture();
    const { queueAudio, setVolume: setPlaybackVolume, stop: stopPlayback } = useAudioPlayback();

    // Handle start call
    const handleStartCall = useCallback(async () => {
        reset();

        if (mode === "voice") {
            // Register audio handler before connecting
            on("audio", (data) => {
                if (data.data) queueAudio(data.data as string);
            });

            connect("voice");

            try {
                await startRecording((audioData) => {
                    sendAudio(audioData);
                });
            } catch {
                console.error("Microphone access denied");
            }
        } else {
            connect("text");
        }
    }, [mode, reset, connect, on, queueAudio, startRecording, sendAudio]);

    // Handle end call
    const handleEndCall = useCallback(() => {
        stopRecording();
        stopPlayback();
        disconnect();
    }, [stopRecording, stopPlayback, disconnect]);

    // Handle text message send
    const handleSendText = useCallback(() => {
        if (!textInput.trim()) return;
        sendText(textInput.trim());

        // Add to local transcript for text mode
        if (mode === "text") {
            useCallStore.getState().addMessage({
                id: crypto.randomUUID(),
                speaker: "user",
                text: textInput.trim(),
                isFinal: true,
                timestamp: new Date().toISOString(),
            });
        }

        setTextInput("");
    }, [textInput, sendText, mode]);

    // Handle volume change
    const handleVolumeChange = useCallback(
        (v: number) => {
            setVolume(v);
            setPlaybackVolume(v);
        },
        [setVolume, setPlaybackVolume]
    );

    // Idle state — show start screen
    if (callStatus === "idle" || callStatus === "ended") {
        return (
            <div className="min-h-screen flex items-center justify-center p-6 relative">
                {/* Background glow */}
                <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] bg-brand-600/20 rounded-full blur-[120px] pointer-events-none" />

                <div className="max-w-md w-full text-center space-y-8 relative z-10 glass-card p-10">
                    {/* Logo / Header */}
                    <div className="space-y-4">
                        <div className="w-24 h-24 mx-auto rounded-3xl bg-gradient-to-br from-brand-400 to-brand-700 flex items-center justify-center shadow-2xl shadow-brand-500/30 ring-1 ring-white/20">
                            <Headphones size={44} className="text-white drop-shadow-md" />
                        </div>
                        <h1 className="text-4xl font-extrabold tracking-tight bg-gradient-to-br from-white via-slate-200 to-brand-300 bg-clip-text text-transparent pb-1">
                            Bank ABC
                        </h1>
                        <p className="text-slate-400 text-base font-medium">
                            AI-Powered Voice Banking Assistant
                        </p>
                    </div>

                    {/* Mode Selector */}
                    <div className="glass-card p-1.5 inline-flex gap-1">
                        <button
                            onClick={() => setMode("text")}
                            className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all ${mode === "text"
                                ? "bg-brand-600 text-white shadow-lg"
                                : "text-slate-400 hover:text-slate-200"
                                }`}
                        >
                            <MessageSquare size={16} />
                            Text
                        </button>
                        <button
                            onClick={() => setMode("voice")}
                            className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-sm font-medium transition-all ${mode === "voice"
                                ? "bg-brand-600 text-white shadow-lg"
                                : "text-slate-400 hover:text-slate-200"
                                }`}
                        >
                            <Headphones size={16} />
                            Voice
                        </button>
                    </div>

                    {/* Start Call Button */}
                    <button
                        onClick={handleStartCall}
                        className="group relative w-full py-4 rounded-2xl bg-gradient-to-r from-brand-600 to-brand-500 text-white font-semibold text-lg shadow-xl shadow-brand-600/30 hover:shadow-brand-500/40 transition-all duration-300 hover:scale-[1.02] active:scale-95 overflow-hidden"
                    >
                        <div className="absolute inset-0 bg-white/20 translate-y-full group-hover:translate-y-0 transition-transform duration-300 ease-in-out" />
                        <div className="relative flex items-center justify-center gap-3">
                            <Phone size={22} className="animate-pulse" />
                            Start {mode === "voice" ? "Voice" : "Text"} Session
                        </div>
                    </button>

                    {callStatus === "ended" && (
                        <p className="text-slate-500 text-sm animate-fade-in">
                            Call ended. Click above to start a new session.
                        </p>
                    )}

                    {/* State Info Badge */}
                    {stateUpdate.intent && (
                        <div className="glass-card px-4 py-3 text-left space-y-1 text-xs text-slate-400">
                            <p>
                                Last intent: <span className="text-brand-400">{stateUpdate.intent}</span>
                            </p>
                            <p>
                                Auth: <span className={stateUpdate.authenticated ? "text-success" : "text-danger"}>
                                    {stateUpdate.authenticated ? "Yes" : "No"}
                                </span>
                            </p>
                        </div>
                    )}
                </div>
            </div>
        );
    }

    // Active call state
    return (
        <div className="min-h-screen flex items-center justify-center p-4 sm:p-8 pt-24">
            <div className="w-full max-w-5xl h-[80vh] min-h-[600px] glass flex flex-col overflow-hidden shadow-2xl ring-1 ring-white/10">
                {/* Header */}
                <header className="flex items-center justify-between px-8 py-5 border-b border-white/5 bg-white/[0.02]">
                    <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-brand-500 to-brand-700 flex items-center justify-center shadow-lg shadow-brand-500/20">
                            <Headphones size={20} className="text-white" />
                        </div>
                        <div>
                            <h1 className="text-base font-semibold text-slate-100">Bank ABC Agent</h1>
                            <p className="text-xs text-slate-400 font-medium">
                                {mode === "voice" ? "Voice" : "Text"} Session
                                {stateUpdate.intent && ` • ${stateUpdate.intent.replace("_", " ")}`}
                            </p>
                        </div>
                    </div>

                    {/* Auth Badge */}
                    {stateUpdate.authenticated && (
                        <span className="px-3 py-1.5 rounded-full bg-success/15 text-success text-xs font-semibold tracking-wide border border-success/20 shadow-sm shadow-success/10">
                            Verified User
                        </span>
                    )}
                </header>

                {/* Main Content */}
                <div className="flex-1 flex flex-col lg:flex-row overflow-hidden">
                    {/* Left: Visualizer + Loading */}
                    <div className="lg:w-2/5 flex flex-col items-center justify-center p-8 gap-8 border-r border-white/5 bg-white/[0.01]">
                        <div className="w-full relative">
                            <div className="absolute inset-0 bg-brand-500/10 blur-3xl rounded-full" />
                            <div className="relative glass-card p-6 w-full border-white/10 shadow-2xl">
                                <AudioVisualizer
                                    analyserNode={analyserNode}
                                    isActive={callStatus === "active"}
                                />
                            </div>
                        </div>

                        {/* Connecting spinner */}
                        {callStatus === "connecting" && (
                            <div className="flex items-center gap-3 text-brand-400 bg-brand-400/10 px-4 py-2 rounded-full border border-brand-400/20">
                                <div className="w-4 h-4 border-2 border-brand-400 border-t-transparent rounded-full animate-spin" />
                                <span className="text-sm font-medium">Connecting…</span>
                            </div>
                        )}
                    </div>

                    {/* Right: Transcript */}
                    <div className="flex-1 flex flex-col bg-surface-base/40 relative">
                        {/* Fade overlay at top of transcript */}
                        <div className="absolute top-0 left-0 right-0 h-8 bg-gradient-to-b from-surface-base to-transparent z-10 pointer-events-none opacity-50" />

                        <TranscriptDisplay messages={messages} />

                        {/* Text input (text mode only) */}
                        {mode === "text" && callStatus === "active" && (
                            <div className="p-5 border-t border-white/5 bg-white/[0.02]">
                                <form
                                    onSubmit={(e) => {
                                        e.preventDefault();
                                        handleSendText();
                                    }}
                                    className="flex gap-3"
                                >
                                    <input
                                        type="text"
                                        value={textInput}
                                        onChange={(e) => setTextInput(e.target.value)}
                                        placeholder="Type your message…"
                                        className="flex-1 bg-surface-elevated/80 border border-white/10 rounded-xl px-5 py-3.5 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-brand-500/50 focus:ring-1 focus:ring-brand-500/30 transition-all shadow-inner"
                                        autoFocus
                                    />
                                    <button
                                        type="submit"
                                        disabled={!textInput.trim()}
                                        className="px-6 py-3.5 rounded-xl bg-brand-600 text-white text-sm font-bold shadow-lg shadow-brand-600/20 hover:bg-brand-500 hover:shadow-brand-500/30 disabled:opacity-30 disabled:cursor-not-allowed transition-all transform hover:scale-[1.02] active:scale-95"
                                    >
                                        Send
                                    </button>
                                </form>
                            </div>
                        )}
                    </div>
                </div>

                {/* Bottom Controls */}
                <div className="border-t border-white/5 bg-white/[0.03]">
                    <CallControls
                        isMuted={isMuted}
                        volume={volume}
                        agentStatus={agentStatus}
                        onToggleMute={toggleMute}
                        onVolumeChange={handleVolumeChange}
                        onHangUp={handleEndCall}
                    />
                </div>
            </div>
        </div>
    );
}
