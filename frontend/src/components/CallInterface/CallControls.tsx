import { Mic, MicOff, Volume2, VolumeX, PhoneOff } from "lucide-react";
import { StatusIndicator } from "./StatusIndicator";
import type { AgentStatus } from "../../stores/callStore";

interface CallControlsProps {
    isMuted: boolean;
    volume: number;
    agentStatus: AgentStatus;
    onToggleMute: () => void;
    onVolumeChange: (v: number) => void;
    onHangUp: () => void;
}

/**
 * Call control bar with mute, volume, status, and hang-up buttons.
 */
export function CallControls({
    isMuted,
    volume,
    agentStatus,
    onToggleMute,
    onVolumeChange,
    onHangUp,
}: CallControlsProps) {
    return (
        <div className="flex items-center justify-between px-6 py-4 glass-card">
            {/* Left: Mic toggle */}
            <button
                onClick={onToggleMute}
                className={`p-3 rounded-full transition-all duration-200 ${isMuted
                        ? "bg-danger/20 text-danger hover:bg-danger/30"
                        : "bg-brand-600/20 text-brand-400 hover:bg-brand-600/30"
                    }`}
                title={isMuted ? "Unmute microphone" : "Mute microphone"}
            >
                {isMuted ? <MicOff size={22} /> : <Mic size={22} />}
            </button>

            {/* Center: Status + Volume */}
            <div className="flex items-center gap-6">
                <StatusIndicator status={agentStatus} />

                <div className="flex items-center gap-2">
                    <button
                        onClick={() => onVolumeChange(volume === 0 ? 1 : 0)}
                        className="text-slate-400 hover:text-slate-200 transition-colors"
                    >
                        {volume === 0 ? <VolumeX size={18} /> : <Volume2 size={18} />}
                    </button>
                    <input
                        type="range"
                        min="0"
                        max="1"
                        step="0.1"
                        value={volume}
                        onChange={(e) => onVolumeChange(parseFloat(e.target.value))}
                        className="w-20 accent-brand-500"
                    />
                </div>
            </div>

            {/* Right: Hang up */}
            <button
                onClick={onHangUp}
                className="p-3 rounded-full bg-danger hover:bg-danger/80 text-white transition-all duration-200 shadow-lg shadow-danger/25"
                title="End call"
            >
                <PhoneOff size={22} />
            </button>
        </div>
    );
}
