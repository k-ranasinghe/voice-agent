import { BrowserRouter, Routes, Route, Link, useLocation } from "react-router-dom";
import { Headphones, LayoutDashboard } from "lucide-react";
import { CallInterface } from "./components/CallInterface/CallInterface";
import { AdminDashboard } from "./components/AdminDashboard/AdminDashboard";

function NavBar() {
  const location = useLocation();

  return (
    <nav className="fixed top-6 left-1/2 -translate-x-1/2 z-50">
      <div className="glass px-2 py-2 flex gap-2 items-center rounded-full shadow-2xl border border-white/10 bg-surface-base/60 backdrop-blur-xl">
        <Link
          to="/"
          className={`flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium transition-all duration-300 ${location.pathname === "/"
            ? "bg-brand-600 text-white shadow-lg shadow-brand-500/25"
            : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
            }`}
        >
          <Headphones size={16} />
          Call
        </Link>
        <div className="w-px h-6 bg-white/10 mx-1"></div>
        <Link
          to="/admin"
          className={`flex items-center gap-2 px-5 py-2.5 rounded-full text-sm font-medium transition-all duration-300 ${location.pathname === "/admin"
            ? "bg-brand-600 text-white shadow-lg shadow-brand-500/25"
            : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
            }`}
        >
          <LayoutDashboard size={16} />
          Admin
        </Link>
      </div>
    </nav>
  );
}

function App() {
  return (
    <BrowserRouter>
      <NavBar />
      <main>
        <Routes>
          <Route path="/" element={<CallInterface />} />
          <Route path="/admin" element={<AdminDashboard />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}

export default App;
