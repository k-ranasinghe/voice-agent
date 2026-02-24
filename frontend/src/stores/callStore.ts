import { create } from "zustand";

export type CallStatus = "idle" | "connecting" | "active" | "ended";
export type AgentStatus = "idle" | "listening" | "thinking" | "speaking" | "error";

export interface TranscriptMessage {
    id: string;
    speaker: "user" | "agent";
    text: string;
    isFinal: boolean;
    timestamp: string;
}

export interface StateUpdate {
    intent: string | null;
    authenticated: boolean;
    flowStage: string | null;
    escalationRequested: boolean;
}

interface CallStore {
    // Connection
    callStatus: CallStatus;
    sessionId: string | null;
    setCallStatus: (status: CallStatus) => void;
    setSessionId: (id: string) => void;

    // Agent
    agentStatus: AgentStatus;
    setAgentStatus: (status: AgentStatus) => void;

    // Transcript
    messages: TranscriptMessage[];
    addMessage: (msg: TranscriptMessage) => void;
    updateLastInterim: (text: string) => void;

    // State
    stateUpdate: StateUpdate;
    setStateUpdate: (update: Partial<StateUpdate>) => void;

    // Audio
    isMuted: boolean;
    volume: number;
    toggleMute: () => void;
    setVolume: (v: number) => void;

    // Reset
    reset: () => void;
}

const initialState = {
    callStatus: "idle" as CallStatus,
    sessionId: null as string | null,
    agentStatus: "idle" as AgentStatus,
    messages: [] as TranscriptMessage[],
    stateUpdate: {
        intent: null,
        authenticated: false,
        flowStage: null,
        escalationRequested: false,
    },
    isMuted: false,
    volume: 1,
};

export const useCallStore = create<CallStore>((set) => ({
    ...initialState,

    setCallStatus: (status) => set({ callStatus: status }),
    setSessionId: (id) => set({ sessionId: id }),
    setAgentStatus: (status) => set({ agentStatus: status }),

    addMessage: (msg) =>
        set((state) => ({
            messages: [...state.messages, msg],
        })),

    updateLastInterim: (text) =>
        set((state) => {
            const msgs = [...state.messages];
            let lastIdx = -1;
            for (let i = msgs.length - 1; i >= 0; i--) {
                if (msgs[i].speaker === "user" && !msgs[i].isFinal) {
                    lastIdx = i;
                    break;
                }
            }
            if (lastIdx >= 0) {
                msgs[lastIdx] = { ...msgs[lastIdx], text };
            } else {
                msgs.push({
                    id: crypto.randomUUID(),
                    speaker: "user",
                    text,
                    isFinal: false,
                    timestamp: new Date().toISOString(),
                });
            }
            return { messages: msgs };
        }),

    setStateUpdate: (update) =>
        set((state) => ({
            stateUpdate: { ...state.stateUpdate, ...update },
        })),

    toggleMute: () => set((state) => ({ isMuted: !state.isMuted })),
    setVolume: (v) => set({ volume: v }),

    reset: () => set(initialState),
}));
