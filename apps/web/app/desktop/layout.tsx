"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export default function DesktopLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();

  const NAV_ITEMS = [
    { label: "Dashboard", href: "/dashboard", icon: "⊞" },
    { label: "Targets", href: "/targets", icon: "👥" },
    { label: "Import", href: "/import", icon: "📥" },
    { label: "Analytics", href: "/analytics", icon: "📊" },
    { label: "Ops", href: "/ops", icon: "⚙️" },
  ];

  return (
    <div className="app-layout">
      <aside className="sidebar">
        <div className="sidebar-logo">
          <span style={{ fontSize: "28px" }}>◎</span> Outreach
        </div>

        <div className="nav-section" style={{ marginTop: "1rem" }}>
          <div className="nav-label">Menu</div>
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.href}
              href={item.href}
              className={`nav-item ${
                pathname === item.href || pathname.startsWith(item.href + "/")
                  ? "active"
                  : ""
              }`}
            >
              <span style={{ width: "20px" }}>{item.icon}</span>
              {item.label}
            </Link>
          ))}
        </div>

        <div className="nav-section" style={{ marginTop: "2rem" }}>
          <div className="nav-label">General</div>
          <Link href="/profile" className={`nav-item ${pathname === "/profile" ? "active" : ""}`}>
            <span style={{ width: "20px" }}>⚙️</span> Settings
          </Link>
          <Link href="#" className="nav-item">
            <span style={{ width: "20px" }}>ℹ️</span> Help
          </Link>
          <form action="/api/auth/signout" method="POST">
            <button type="submit" className="nav-item" style={{ background: "transparent", width: "100%", border: "none", textAlign: "left", fontSize: "14px", fontFamily: "inherit" }}>
              <span style={{ width: "20px" }}>🚪</span> Logout
            </button>
          </form>
        </div>

        <div className="dz-card dz-card-dark" style={{ marginTop: "auto", padding: "1.25rem", borderRadius: "1rem" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.5rem" }}>
            <span style={{ background: "rgba(255,255,255,0.2)", borderRadius: "50%", width: "24px", height: "24px", display: "flex", alignItems: "center", justifyContent: "center", fontSize: "12px" }}>◎</span>
          </div>
          <h4 style={{ fontSize: "16px", marginBottom: "0.5rem" }}>Download our<br/>Mobile App</h4>
          <p style={{ fontSize: "11px", color: "rgba(255,255,255,0.8)", marginBottom: "1rem" }}>Get easy in another way</p>
          <button className="primary" style={{ width: "100%", background: "rgba(255,255,255,0.2)", backdropFilter: "blur(4px)" }}>
            Download
          </button>
        </div>
      </aside>

      <div style={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
        <header className="topbar">
          <div className="search-bar">
            <span>🔍</span>
            <input type="text" placeholder="Search task" />
            <span className="search-shortcut">⌘F</span>
          </div>

          <div className="topbar-actions">
            <button className="icon-btn">✉️</button>
            <button className="icon-btn">🔔</button>
            <div className="user-profile">
              <div className="avatar">A</div>
              <div style={{ paddingRight: "0.5rem" }}>
                <div style={{ fontSize: "13px", fontWeight: "600", color: "var(--fg)" }}>User</div>
                <div style={{ fontSize: "11px", color: "var(--muted)" }}>user@mail.com</div>
              </div>
            </div>
          </div>
        </header>

        <main className="main-content">
          {children}
        </main>
      </div>
    </div>
  );
}
