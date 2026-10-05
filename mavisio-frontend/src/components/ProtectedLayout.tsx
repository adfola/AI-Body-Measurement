import { Activity, Users, LogOut, Scissors, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useEffect, useState } from "react";
import { NavLink, Navigate, Outlet } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Button } from "./ui/button";

export default function ProtectedLayout() {
  const { token, logout } = useAuth();
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isMobile, setIsMobile] = useState(false);

  useEffect(() => {
    const media = window.matchMedia("(max-width: 800px)");
    const syncViewport = () => {
      setIsMobile(media.matches);
      setSidebarOpen(!media.matches);
    };
    syncViewport();
    media.addEventListener("change", syncViewport);
    return () => media.removeEventListener("change", syncViewport);
  }, []);

  if (!token) return <Navigate to="/login" replace />;

  return (
    <div className={`app-shell ${isMobile ? "sidebar-mobile" : ""} ${sidebarOpen ? "sidebar-open" : "sidebar-closed"}`}>
      {isMobile && sidebarOpen && <button className="sidebar-backdrop" aria-label="Close navigation" onClick={() => setSidebarOpen(false)} />}
      <aside className="sidebar" id="main-sidebar">
        <NavLink to="/" className="brand-lockup" aria-label="Mavisio home">
          <span className="brand-mark"><Scissors size={19} strokeWidth={1.8} /></span>
          <span className="brand-label"><strong>MAVISIO</strong><small>MEASUREMENT STUDIO</small></span>
        </NavLink>
        <div className="side-caption">WORKSPACE</div>
        <nav className="side-nav" aria-label="Main navigation">
          <NavLink to="/" end aria-label="Clients" title="Clients" onClick={() => isMobile && setSidebarOpen(false)} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
            <Users size={17} /> <span className="nav-label">Clients</span>
          </NavLink>
          <NavLink to="/studio" aria-label="Measurement studio" title="Measurement studio" onClick={() => isMobile && setSidebarOpen(false)} className={({ isActive }) => `nav-link ${isActive ? "active" : ""}`}>
            <Activity size={17} /> <span className="nav-label">Measurement studio</span>
          </NavLink>
        </nav>
        <div className="sidebar-bottom">
          <span className="status-dot" /> <span className="service-label">Local service</span>
          <span className="service-url">localhost:8000</span>
        </div>
      </aside>
      <div className="main-column">
        <header className="topbar">
          <div className="topbar-start">
            <Button variant="ghost" size="icon" className="sidebar-toggle" onClick={() => setSidebarOpen((open) => !open)} aria-label={sidebarOpen ? "Close sidebar" : "Open sidebar"} aria-expanded={sidebarOpen} aria-controls="main-sidebar">
              {sidebarOpen ? <PanelLeftClose size={18} /> : <PanelLeftOpen size={18} />}
            </Button>
            <span className="topbar-context">TAILOR WORKSPACE <span>/</span> MAVISIO</span>
          </div>
          <Button variant="ghost" size="sm" onClick={logout} aria-label="Log out">
            <LogOut size={16} /> <span>Log out</span>
          </Button>
        </header>
        <main className="page-content"><Outlet /></main>
      </div>
    </div>
  );
}
