import { useEffect, useState } from "react";
import { Overview } from "./pages/Overview";
import { Scopes } from "./pages/Scopes";
import { Evidence } from "./pages/Evidence";
import { ReplayPage } from "./pages/Replay";
import { provenance } from "./data/task007";

export type Page = "overview" | "scopes" | "evidence" | "replay";
const PAGES: { id: Page; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "scopes", label: "Scope comparison" },
  { id: "evidence", label: "Evidence & method" },
  { id: "replay", label: "Recorded replay" },
];
const fromHash = (): Page => {
  const h = window.location.hash.replace(/^#\/?/, "");
  return (PAGES.find((p) => p.id === h)?.id ?? "overview") as Page;
};

export default function App() {
  const [page, setPage] = useState<Page>(fromHash);
  useEffect(() => {
    const on = () => setPage(fromHash());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  const go = (p: Page) => {
    window.location.hash = `/${p}`;
    setPage(p);
    window.scrollTo({ top: 0 });
  };
  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="site">
        <div className="wrap head">
          <div>
            <p className="brand">Agent Readiness <span className="tag">diagnostic dashboard</span></p>
            <p className="sub">What a Meta Muse Spark shopping agent did on a controlled storefront, why, and what a site owner could change.</p>
          </div>
          <p className="badge" role="note">Recorded experiment data · Task 007 · not live inference</p>
        </div>
        <nav className="wrap" aria-label="Sections">
          <ul className="tabs">
            {PAGES.map((p) => (
              <li key={p.id}>
                <a href={`#/${p.id}`} aria-current={page === p.id ? "page" : undefined} onClick={(e) => { e.preventDefault(); go(p.id); }}>{p.label}</a>
              </li>
            ))}
          </ul>
        </nav>
      </header>
      <main id="main" className="wrap" tabIndex={-1}>
        {page === "overview" && <Overview go={(p) => go(p)} />}
        {page === "scopes" && <Scopes />}
        {page === "evidence" && <Evidence />}
        {page === "replay" && <ReplayPage />}
      </main>
      <footer className="site"><div className="wrap">
        <p>Controlled synthetic storefront (20 products) · Meta Muse Spark <code>{provenance.model}</code> reference agent · executed from commit <code>{provenance.executionCommit}</code> · costs are calculated estimates, not bills · no universal readiness score, no claims about real websites.</p>
      </div></footer>
    </>
  );
}
