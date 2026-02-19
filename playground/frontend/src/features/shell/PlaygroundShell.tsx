"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { usePlayground } from "../core/PlaygroundProvider";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/remember", label: "Remember" },
  { href: "/catalog", label: "References" },
  { href: "/contacts", label: "Contacts" },
  { href: "/inbox", label: "Inbox" },
  { href: "/calendar", label: "Calendar" },
  { href: "/chat", label: "Chat" },
];

const DASHBOARD_ITEMS = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/chat", label: "Chat" },
];

export default function PlaygroundShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { userId, setUserId, loading, error, notice, reloadAll } = usePlayground();
  const isDashboard = pathname === "/dashboard";
  const navItems = isDashboard ? DASHBOARD_ITEMS : NAV_ITEMS;

  return (
    <main className={`app-shell ${isDashboard ? "app-shell-light" : ""}`}>
      <aside className={`app-sidebar ${isDashboard ? "app-sidebar-light" : ""}`}>
        <div className="memory-header">
          <div>
            <p className="eyebrow">EA Diary</p>
            <h1 className="memory-title">A calm place for clarity</h1>
          </div>
          <span className="chip">Diary</span>
        </div>

        <section className="memory-block">
          <div className="row">
            <input
              className="input"
              placeholder="EA profile"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
            />
            <button className="button secondary" onClick={() => void reloadAll()}>
              Refresh
            </button>
          </div>
          {notice ? <div className="notice">{notice}</div> : null}
          {error ? <div className="notice">{error}</div> : null}
          {loading ? <div className="notice">Loading...</div> : null}
        </section>

        <section className="memory-block">
          <nav className="quick-actions">
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`chip ghost ${pathname === item.href ? "active-tab" : ""}`}
              >
                {item.label}
              </Link>
            ))}
          </nav>
        </section>
      </aside>

      <section className="app-main">
        {children}
      </section>
    </main>
  );
}
