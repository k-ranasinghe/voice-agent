const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export interface ActiveCall {
    session_id: string;
    customer_id: string | null;
    intent: string | null;
    authenticated: boolean;
    started_at: string;
    duration: number | null;
}

export interface Configuration {
    id: string;
    key: string;
    value: string;
    category: string;
    updated_at: string;
}

export interface CallHistoryItem {
    session_id: string;
    customer_id: string | null;
    intent: string | null;
    authenticated: boolean;
    escalated: boolean;
    started_at: string;
    ended_at: string | null;
    duration: number | null;
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
    const res = await fetch(`${API_URL}${path}`, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });
    if (!res.ok) throw new Error(`API Error ${res.status}: ${res.statusText}`);
    return res.json();
}

export const api = {
    // Health
    health: () => request<Record<string, unknown>>("/health"),

    // Admin
    getActiveCalls: () =>
        request<{ active_sessions: ActiveCall[] }>("/api/admin/active-calls"),

    getConfigurations: () =>
        request<{ configurations: Configuration[] }>("/api/admin/configurations"),

    updateConfiguration: (key: string, value: string) =>
        request<{ status: string }>("/api/admin/configurations", {
            method: "PUT",
            body: JSON.stringify({ key, value }),
        }),

    getCallHistory: (limit = 50) =>
        request<{ sessions: CallHistoryItem[] }>(
            `/api/admin/call-history?limit=${limit}`
        ),
};
