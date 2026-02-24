import { useEffect, useRef } from "react";
import { User, Headphones } from "lucide-react";
import type { TranscriptMessage } from "../../stores/callStore";

interface TranscriptDisplayProps {
    messages: TranscriptMessage[];
}

/**
 * Scrolling transcript panel showing user and agent messages.
 * User messages right-aligned (blue), agent messages left-aligned (slate).
 */
export function TranscriptDisplay({ messages }: TranscriptDisplayProps) {
    const bottomRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    if (messages.length === 0) {
        return (
            <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
                <p>Conversation will appear here…</p>
            </div>
        );
    }

    return (
        <div className="flex-1 overflow-y-auto space-y-4 p-6 pt-10">
            {messages.map((msg) => (
                <div
                    key={msg.id}
                    className={`flex items-end gap-3 ${msg.speaker === "user" ? "flex-row-reverse" : "flex-row"} animate-fade-in`}
                >
                    {/* Avatar */}
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 shadow-md ${msg.speaker === "user"
                            ? "bg-brand-600 shadow-brand-500/30"
                            : "bg-surface-elevated border border-white/10"
                        }`}>
                        {msg.speaker === "user" ? (
                            <User size={14} className="text-white" />
                        ) : (
                            <Headphones size={14} className="text-brand-300" />
                        )}
                    </div>

                    {/* Message Bubble */}
                    <div
                        className={`max-w-[75%] px-5 py-3.5 rounded-2xl shadow-sm ${msg.speaker === "user"
                                ? "bg-brand-600 text-white rounded-br-sm shadow-brand-600/20"
                                : "bg-surface-elevated/80 text-slate-200 rounded-bl-sm border border-white/5"
                            } ${!msg.isFinal ? "opacity-60 italic" : ""}`}
                    >
                        <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.text}</p>
                        <p
                            className={`text-[10px] mt-2 font-medium tracking-wide ${msg.speaker === "user" ? "text-brand-200/80" : "text-slate-500"
                                }`}
                        >
                            {new Date(msg.timestamp).toLocaleTimeString([], {
                                hour: "2-digit",
                                minute: "2-digit",
                            })}
                        </p>
                    </div>
                </div>
            ))}
            <div ref={bottomRef} className="h-4" />
        </div>
    );
}
