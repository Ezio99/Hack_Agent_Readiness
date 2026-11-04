import { SiteFooter, SiteHeader } from '../Shell';
import { HostedEvaluation } from './HostedEvaluation';
import './workspace.css';

/** `#/run` and `#/run/eval-<id>`: the operator/visitor evaluation workspace over the hosted API. */
export function Workspace({ job }: { job: string | null }) {
  return <div className="ar ws">
    <a className="ar-skip" href="#ws-main" onClick={e => { e.preventDefault(); document.getElementById('ws-main')?.focus(); }}>Skip to content</a>
    <SiteHeader active="run" cta={false} />
    <main id="ws-main" tabIndex={-1} className="wrap ws-wrap">
      <HostedEvaluation initialJob={job} onOpen={() => {}} />
    </main>
    <SiteFooter />
  </div>;
}
