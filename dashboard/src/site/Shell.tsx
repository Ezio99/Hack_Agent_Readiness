import './site.css';
import { useEffect, useState } from 'react';
import fontLicense from './fonts/OFL-Newsreader.txt?url';
import monoLicense from './fonts/OFL-GeistMono.txt?url';
import sansLicense from './fonts/OFL-Geist.txt?url';
import { CANONICAL, FEATURED } from './showcase';

/** The mark: a viewport with the agent's focus in one quadrant. */
export function Mark({ className = 'brand-mark' }: { className?: string }) {
  return <svg className={className} viewBox="0 0 18 18" aria-hidden="true">
    <rect x=".75" y=".75" width="16.5" height="16.5" rx="2.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
    <rect x="9" y="9" width="6.5" height="6.5" rx="1" fill="var(--signal)" />
  </svg>;
}

export function Brand() {
  return <a className="brand" href="#/" aria-label="Agent Readiness home"><Mark />Agent Readiness</a>;
}

type Active = 'home' | 'demo' | 'run' | 'lifecycle' | 'report' | 'showcase';
/** The judge-facing header: what it is, the evidence, the application, and one primary action. The Showcase, the journey and the latest live report stay
 *  reachable from the footer and the pages that cite them (their routes are unchanged). */
const RESULTS_HREF = `#/reports/${CANONICAL.id}`;   // the canonical paired Before vs After evaluation (not #/reports/latest, which may be a later run)
export const REPO_URL = 'https://github.com/Ezio99/Hack_Agent_Readiness';
const NAV: { id: Active | 'how'; href: string; label: string }[] = [
  { id: 'how', href: '#/how', label: 'How it works' },
  { id: 'report', href: RESULTS_HREF, label: 'See the results' },   // 'report' is active only on the canonical report (ReportPage)
  { id: 'run', href: '#/run', label: 'Workspace' },
];

export function SiteHeader({ active, cta = true }: { active?: Active; cta?: boolean }) {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 8);
    on(); window.addEventListener('scroll', on, { passive: true });
    return () => window.removeEventListener('scroll', on);
  }, []);
  useEffect(() => { const close = () => setOpen(false); window.addEventListener('hashchange', close); return () => window.removeEventListener('hashchange', close); }, []);
  return <header className={`site-head${scrolled ? ' scrolled' : ''}`}>
    <div className="wrap">
      <Brand />
      <button className="menu-btn" aria-expanded={open} aria-controls="site-nav" onClick={() => setOpen(o => !o)}>{open ? 'Close' : 'Menu'}</button>
      <nav id="site-nav" className={`site-nav${open ? ' open' : ''}`} aria-label="Primary">
        {NAV.map(n => <a key={n.id} href={n.href} aria-current={active === n.id ? 'page' : undefined}>{n.label}</a>)}
        {cta && <a className="nav-cta" href="#/run">Run an evaluation <span className="arr" aria-hidden="true">→</span></a>}{/* the CTA inside the mobile menu */}
      </nav>
      {cta && <a className="btn btn-sm btn-signal" href="#/run">Run an evaluation <span className="arr" aria-hidden="true">→</span></a>}
    </div>
  </header>;
}

export function SiteFooter() {
  return <footer className="site-foot">
    <div className="wrap">
      <div><Brand /><p className="about">Agent Readiness measures whether AI agents can complete real tasks on a website, where they struggle, and whether a change helps.</p></div>
      <div><h4>Product</h4><ul><li><a href="#/lifecycle">The {FEATURED.short} journey</a></li><li><a href="#/run">Run an evaluation</a></li><li><a href="#/showcase">Before and after</a></li></ul></div>
      <div><h4>Evidence</h4><ul><li><a href={RESULTS_HREF}>Canonical evaluation results</a></li><li><a href="#/reports/latest">Latest live report</a></li></ul></div>
      <div><h4>About</h4><ul><li><a href="#/how">How it works</a></li><li><a href="#/trust">Isolation &amp; limitations</a></li><li><a href={REPO_URL} target="_blank" rel="noopener noreferrer">GitHub repository</a></li></ul></div>
      <div className="fine"><span>Built for the Meta Global AI Hackathon, 2026. Model costs shown are calculated estimates, not bills.</span>
        <span>Type: <a href={fontLicense}>Newsreader</a>, <a href={sansLicense}>Geist</a>, <a href={monoLicense}>Geist Mono</a> (SIL OFL)</span></div>
    </div>
  </footer>;
}
