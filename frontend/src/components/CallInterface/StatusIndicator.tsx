import type { AgentStatus } from "../../stores/callStore";

interface StatusIndicatorProps {
    status: AgentStatus;
}

const statusConfig: Record<AgentStatus, { label: string; color: string; pulse: boolean }> = {
    idle: { label: "Ready", color: "bg-success", pulse: false },
    listening: { label: "Listening…", color: "bg-success", pulse: true },
    thinking: { label: "Thinking…", color: "bg-warning", pulse: true },
    speaking: { label: "Speaking…", color: "bg-brand-500", pulse: true },
    error: { label: "Error", color: "bg-danger", pulse: false },
};

/**
 * Animated status dot with label showing agent's current state.
 */
export function StatusIndicator({ status }: StatusIndicatorProps) {
    const config = statusConfig[status];

    return (
        <div className="flex items-center gap-2">
            <span className="relative flex h-3 w-3">
                {config.pulse && (
                    <span
                        className={`absolute inline-flex h-full w-full rounded-full ${config.color} opacity-75 animate-ping`}
                    />
                )}
                <span
                    className={`relative inline-flex rounded-full h-3 w-3 ${config.color}`}
                />
            </span>
            <span className="text-sm text-slate-400">{config.label}</span>
        </div>
    );
}
