import { ReplayStudio } from "./studio/ReplayStudio";
import { useEffect, useState } from "react";
import { Overview } from "./pages/Overview";
import { Scopes } from "./pages/Scopes";
import { Evidence } from "./pages/Evidence";
import { ReplayPage } from "./pages/Replay";
import { ScannerPage } from "./pages/Scanner";
import { InvestigationPage } from "./pages/Investigation";
import { provenance } from "./data/task007";

export type Page = "studio" | "overview" | "scopes" | "evidence" | "replay" | "scanner" | "investigation";
const MAIN: { id: Page; label: string } = { id: "investigation", label: "Investigation" };
/** Earlier experiments, kept as a secondary section. */
const HISTORICAL: { id: Page; label: string }[] = [
  { id: "overview", label: "Task 007 overview" },
  { id: "scopes", label: "Scope comparison" },
  { id: "evidence", label: "Evidence & method" },
  { id: "replay", label: "Recorded replay" },
  { id: "scanner", label: "Protected scanner" },
];
const PAGES = [{ id: "studio" as Page, label: "Replay Studio" }, MAIN, ...HISTORICAL];
const runJob = (): string | null | undefined => {
  const m = window.location.hash.match(/^#\/run(?:\/(eval-[0-9a-f]{32}))?$/);
  return m ? (m[1] ?? null) : undefined;
};
const fromHash = (): Page => {
  const h = window.location.hash.replace(/^#\/?/, "");
  if (runJob() !== undefined) return "studio";
  return (PAGES.find((p) => p.id === h)?.id ?? "studio") as Page;
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
  if (page === "studio") return <ReplayStudio openReport={() => go("investigation")} runJob={runJob()} />;
  return (
    <>
      <a className="skip" href="#main">Skip to content</a>
      <header className="site">
        <div className="wrap head">
          <div>
            <p className="brand">Agent Readiness <span className="tag">diagnostic dashboard</span></p>
            <p className="sub">{page === "investigation" ? "Test website → Discover friction → Explore improvements → Measure impact." : "What a Meta Muse Spark shopping agent did on a controlled storefront, why, and what a site owner could change."}</p>
          </div>
          <p className="badge" role="note">{page === "investigation" ? "Recorded Ironbark demo" : "Recorded experiment data · Task 007 · not live inference"}</p>
        </div>
        <nav className="wrap" aria-label="Sections">
          <ul className="tabs"><li><a href="#/studio" onClick={e => { e.preventDefault(); go("studio"); }}>Replay Studio</a></li>
            <li><a href={`#/${MAIN.id}`} aria-current={page === MAIN.id ? "page" : undefined} onClick={(e) => { e.preventDefault(); go(MAIN.id); }}>{MAIN.label}</a></li>
            <li className="history-menu"><details><summary>Historical experiments</summary><ul>
            {HISTORICAL.map((p) => (
              <li key={p.id}>
                <a href={`#/${p.id}`} aria-current={page === p.id ? "page" : undefined} onClick={(e) => { e.preventDefault(); go(p.id); }} className="nav-secondary-link">{p.label}</a>
              </li>
            ))}
            </ul></details></li>
          </ul>
        </nav>
      </header>
      <main id="main" className="wrap" tabIndex={-1}>
        {page === "overview" && <Overview go={(p) => go(p)} />}
        {page === "scopes" && <Scopes />}
        {page === "evidence" && <Evidence />}
        {page === "replay" && <ReplayPage />}
        {page === "scanner" && <ScannerPage />}
        {page === "investigation" && <InvestigationPage />}
      </main>
      <footer className="site"><div className="wrap">
        <p>{page === "investigation" ? <>Agent Readiness · Recorded evaluation · Experiment details available in the report</> : <>Controlled synthetic storefront (20 products) · Meta Muse Spark <code>{provenance.model}</code> reference agent · executed from commit <code>{provenance.executionCommit}</code> · costs are calculated estimates, not bills · no universal readiness score, no claims about real websites.</>}</p>
      </div></footer>
    </>
  );
}
