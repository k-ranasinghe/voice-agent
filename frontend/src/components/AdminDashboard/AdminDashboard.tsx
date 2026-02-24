import { useState, useEffect, useCallback } from "react";
import {
    Phone,
    Settings,
    BarChart3,
    RefreshCw,
    Shield,
    Clock,
    User,
} from "lucide-react";
import { api } from "../../services/api";
import type { ActiveCall, Configuration, CallHistoryItem } from "../../services/api";

type Tab = "calls" | "config" | "history";

/**
 * Admin dashboard with tabs for active calls, configuration, and call history.
 */
export function AdminDashboard() {
    const [activeTab, setActiveTab] = useState<Tab>("calls");
    const [activeCalls, setActiveCalls] = useState<ActiveCall[]>([]);
    const [configurations, setConfigurations] = useState<Configuration[]>([]);
    const [history, setHistory] = useState<CallHistoryItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [editingConfig, setEditingConfig] = useState<string | null>(null);
    const [configValue, setConfigValue] = useState("");

    // Fetch data based on active tab
    const fetchData = useCallback(async () => {
        setLoading(true);
        try {
            switch (activeTab) {
                case "calls": {
                    const data = await api.getActiveCalls();
                    setActiveCalls(data.active_sessions || []);
                    break;
                }
                case "config": {
                    const data = await api.getConfigurations();
                    setConfigurations(data.configurations || []);
                    break;
                }
                case "history": {
                    const data = await api.getCallHistory();
                    setHistory(data.sessions || []);
                    break;
                }
            }
        } catch (error) {
            console.error("Failed to fetch data:", error);
        }
        setLoading(false);
    }, [activeTab]);

    useEffect(() => {
        fetchData();
        // Auto-refresh for active calls
        if (activeTab === "calls") {
            const interval = setInterval(fetchData, 5000);
            return () => clearInterval(interval);
        }
    }, [activeTab, fetchData]);

    // Save configuration
    const handleSaveConfig = async (key: string) => {
        try {
            await api.updateConfiguration(key, configValue);
            setEditingConfig(null);
            fetchData();
        } catch (error) {
            console.error("Failed to update config:", error);
        }
    };

    const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
        { id: "calls", label: "Active Calls", icon: <Phone size={16} /> },
        { id: "config", label: "Configuration", icon: <Settings size={16} /> },
        { id: "history", label: "Call History", icon: <BarChart3 size={16} /> },
    ];

    return (
        <div className="min-h-screen p-6">
            <div className="max-w-6xl mx-auto space-y-6">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-2xl font-bold text-slate-100">
                            Admin Dashboard
                        </h1>
                        <p className="text-sm text-slate-500 mt-1">
                            Bank ABC Voice Agent Management
                        </p>
                    </div>
                    <button
                        onClick={fetchData}
                        disabled={loading}
                        className="flex items-center gap-2 px-4 py-2 glass-card text-slate-300 hover:text-white text-sm transition-all"
                    >
                        <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
                        Refresh
                    </button>
                </div>

                {/* Tab Bar */}
                <div className="glass-card p-1.5 inline-flex gap-1 relative z-10 w-full sm:w-auto overflow-x-auto no-scrollbar">
                    {tabs.map((tab) => (
                        <button
                            key={tab.id}
                            onClick={() => setActiveTab(tab.id)}
                            className={`flex items-center justify-center min-w-[120px] gap-2 px-5 py-3 rounded-xl text-sm font-semibold transition-all duration-300 ${activeTab === tab.id
                                ? "bg-brand-600 text-white shadow-lg shadow-brand-500/25"
                                : "text-slate-400 hover:text-slate-100 hover:bg-white/5"
                                }`}
                        >
                            {tab.icon}
                            {tab.label}
                        </button>
                    ))}
                </div>

                {/* Content */}
                <div className="glass shadow-2xl ring-1 ring-white/10 p-6 sm:p-8 min-h-[500px]">
                    {/* Active Calls Tab */}
                    {activeTab === "calls" && (
                        <div className="animate-fade-in">
                            <div className="flex items-center justify-between mb-6 pb-4 border-b border-white/5">
                                <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
                                    <Phone className="text-brand-400" size={20} />
                                    Active Sessions
                                </h2>
                                <span className="px-4 py-1.5 rounded-full bg-brand-600/10 text-brand-400 text-sm font-bold tracking-wide border border-brand-500/20">
                                    {activeCalls.length} Live
                                </span>
                            </div>

                            {activeCalls.length === 0 ? (
                                <div className="flex flex-col items-center justify-center py-16 text-slate-500 space-y-4">
                                    <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center">
                                        <Phone size={24} className="text-slate-600" />
                                    </div>
                                    <p className="text-sm font-medium">No active calls right now</p>
                                </div>
                            ) : (
                                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-1">
                                    {activeCalls.map((call) => (
                                        <div
                                            key={call.session_id}
                                            className="flex items-center justify-between p-4 rounded-xl bg-surface-elevated/50 border border-white/5"
                                        >
                                            <div className="flex items-center gap-4">
                                                <div className="w-10 h-10 rounded-full bg-brand-600/20 flex items-center justify-center">
                                                    <User size={18} className="text-brand-400" />
                                                </div>
                                                <div>
                                                    <p className="text-sm font-medium text-slate-200">
                                                        {call.customer_id || "Unknown"}
                                                    </p>
                                                    <p className="text-xs text-slate-500">
                                                        {call.session_id.slice(0, 8)}…
                                                    </p>
                                                </div>
                                            </div>

                                            <div className="flex items-center gap-3">
                                                {call.intent && (
                                                    <span className="px-3 py-1 rounded-full bg-info/15 text-info text-xs font-medium border border-info/20 shadow-sm shadow-info/10">
                                                        {call.intent}
                                                    </span>
                                                )}
                                                {call.authenticated && (
                                                    <Shield size={14} className="text-success" />
                                                )}
                                                <div className="flex items-center gap-1 text-slate-500 text-xs">
                                                    <Clock size={12} />
                                                    {new Date(call.started_at).toLocaleTimeString()}
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Configuration Tab */}
                    {activeTab === "config" && (
                        <div className="animate-fade-in">
                            <div className="flex items-center justify-between mb-6 pb-4 border-b border-white/5">
                                <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
                                    <Settings className="text-brand-400" size={20} />
                                    System Configuration
                                </h2>
                            </div>

                            {configurations.length === 0 ? (
                                <div className="flex flex-col items-center justify-center py-16 text-slate-500 space-y-4">
                                    <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center">
                                        <Settings size={24} className="text-slate-600" />
                                    </div>
                                    <p className="text-sm font-medium">No configurations found</p>
                                </div>
                            ) : (
                                <div className="grid gap-4 md:grid-cols-2">
                                    {configurations.map((config) => (
                                        <div
                                            key={config.id}
                                            className="p-5 rounded-2xl bg-surface-elevated/40 border border-white/5 shadow-sm hover:bg-surface-elevated/60 transition-colors"
                                        >
                                            <div className="flex items-center justify-between mb-2">
                                                <div>
                                                    <p className="text-sm font-medium text-slate-200">
                                                        {config.key}
                                                    </p>
                                                    <p className="text-xs text-slate-500">
                                                        {config.category}
                                                    </p>
                                                </div>
                                                <button
                                                    onClick={() => {
                                                        setEditingConfig(config.key);
                                                        setConfigValue(config.value);
                                                    }}
                                                    className="px-3 py-1.5 rounded-lg bg-brand-600/10 text-brand-400 text-xs hover:bg-brand-600/20 transition-colors"
                                                >
                                                    Edit
                                                </button>
                                            </div>

                                            {editingConfig === config.key ? (
                                                <div className="flex gap-2 mt-2">
                                                    <textarea
                                                        value={configValue}
                                                        onChange={(e) => setConfigValue(e.target.value)}
                                                        className="flex-1 bg-surface-base border border-white/10 rounded-lg px-3 py-2 text-sm text-slate-200 focus:outline-none focus:border-brand-500/50 min-h-[60px]"
                                                    />
                                                    <div className="flex flex-col gap-1">
                                                        <button
                                                            onClick={() => handleSaveConfig(config.key)}
                                                            className="px-3 py-1.5 rounded-lg bg-success/20 text-success text-xs"
                                                        >
                                                            Save
                                                        </button>
                                                        <button
                                                            onClick={() => setEditingConfig(null)}
                                                            className="px-3 py-1.5 rounded-lg bg-danger/20 text-danger text-xs"
                                                        >
                                                            Cancel
                                                        </button>
                                                    </div>
                                                </div>
                                            ) : (
                                                <p className="text-xs text-slate-400 mt-1 font-mono truncate">
                                                    {config.value}
                                                </p>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    )}

                    {/* Call History Tab */}
                    {activeTab === "history" && (
                        <div className="animate-fade-in">
                            <div className="flex items-center justify-between mb-6 pb-4 border-b border-white/5">
                                <h2 className="text-xl font-bold text-slate-100 flex items-center gap-2">
                                    <BarChart3 className="text-brand-400" size={20} />
                                    Recent Calls
                                </h2>
                                <span className="px-4 py-1.5 rounded-full bg-surface-elevated text-slate-300 text-sm font-medium border border-white/10">
                                    {history.length} records
                                </span>
                            </div>

                            {history.length === 0 ? (
                                <div className="flex flex-col items-center justify-center py-16 text-slate-500 space-y-4">
                                    <div className="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center">
                                        <BarChart3 size={24} className="text-slate-600" />
                                    </div>
                                    <p className="text-sm font-medium">No call history found</p>
                                </div>
                            ) : (
                                <div className="overflow-x-auto rounded-xl border border-white/5 bg-surface-elevated/20">
                                    <table className="w-full text-sm text-left">
                                        <thead className="bg-surface-elevated/50">
                                            <tr className="text-slate-400 text-xs font-semibold tracking-wider uppercase">
                                                <th className="py-4 px-5">Session</th>
                                                <th className="py-4 px-5">Customer</th>
                                                <th className="py-4 px-5">Intent</th>
                                                <th className="py-4 px-5">Auth</th>
                                                <th className="py-4 px-5">Duration</th>
                                                <th className="py-4 px-5">Time</th>
                                            </tr>
                                        </thead>
                                        <tbody className="divide-y divide-white/5">
                                            {history.map((item) => (
                                                <tr
                                                    key={item.session_id}
                                                    className="text-slate-300 hover:bg-white/[0.02] transition-colors"
                                                >
                                                    <td className="py-4 px-5 font-mono text-xs text-slate-400">
                                                        {item.session_id.slice(0, 8)}…
                                                    </td>
                                                    <td className="py-4 px-5 font-medium">
                                                        {item.customer_id || "—"}
                                                    </td>
                                                    <td className="py-4 px-5">
                                                        {item.intent ? (
                                                            <span className="px-2.5 py-1 rounded-full bg-info/10 text-info text-xs font-medium border border-info/20">
                                                                {item.intent}
                                                            </span>
                                                        ) : (
                                                            "—"
                                                        )}
                                                    </td>
                                                    <td className="py-4 px-5">
                                                        {item.authenticated ? (
                                                            <div className="flex items-center gap-1.5 text-success">
                                                                <Shield size={14} />
                                                                <span className="text-xs font-medium">Yes</span>
                                                            </div>
                                                        ) : (
                                                            <span className="text-slate-600">—</span>
                                                        )}
                                                    </td>
                                                    <td className="py-4 px-5 text-xs text-slate-400">
                                                        {item.duration
                                                            ? `${item.duration}s`
                                                            : "—"}
                                                    </td>
                                                    <td className="py-4 px-5 text-xs text-slate-500">
                                                        {new Date(item.started_at).toLocaleString()}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
