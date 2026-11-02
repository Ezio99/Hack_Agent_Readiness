import { useEffect, useRef, useState } from 'react';

/** Real agent telemetry for one trial: page, screenshot, actions, the model's stated goals, errors.
 *  Everything comes from the server's allowlisted projection of the trial trace. */

export interface Action { name: string; target: string | null }
export interface Step { step: number; path: string | null; title: string | null; screenshot: string | null; assessment: string | null; memory: string | null; goal: string | null; actions: Action[]; error: string | null; done: boolean }
export interface Trial { repetition: number; arm: 'original' | 'modified'; task: number; state: string; question?: string | null; mode?: string | null; steps: Step[]; current: { step: number; path: string | null; title: string | null; screenshot: string | null } | null; errors: string[] }
export interface Selection { repetition: number; arm: 'original' | 'modified'; task: number }

const ARM = { original: 'Original', modified: 'Modified' } as const;
const ICON: Record<string, string> = { Navigate: '↗', Click: '◉', Scroll: '↕', 'Find elements': '⌕', 'Search page': '⌕', Extract: '⇲', 'Find text': '⌕', 'Go back': '←', Answer: '✓', Type: '⌨', Wait: '…' };

export function TrialView({ jobId, trial, live, scripted }: { jobId: string; trial: Trial; live: boolean; scripted: boolean }) {
  const [picked, setPicked] = useState<number | null>(null);
  const list = useRef<HTMLOListElement>(null);
  const steps = trial.steps;
  useEffect(() => { setPicked(null); }, [trial.repetition, trial.arm, trial.task]);
  useEffect(() => { if (picked === null && list.current) list.current.scrollTop = list.current.scrollHeight; }, [steps.length, picked]);
  const latest = trial.current ?? (steps.length ? steps[steps.length - 1] : null);
  const shown = picked !== null ? steps.find(s => s.step === picked) ?? latest : latest;
  const shot = shown?.screenshot ? `/api/ironbark/jobs/${jobId}/repetitions/${trial.repetition}/trials/${trial.arm}/${trial.task}/screenshots/${shown.screenshot}` : null;
  const answer = steps.find(s => s.done)?.actions.find(a => a.name === 'Answer')?.target;
  const memory = shown && 'memory' in shown ? (shown as Step).memory : null;
  return <section className="ws-agent" aria-label="Agent activity">
    <header className="ws-agent-head">
      <div><p className="eyebrow">{live ? <><span className="ws-live" aria-hidden="true" /> Live agent</> : 'Agent run'} · Repetition {trial.repetition} · <span className={`arm-${trial.arm}`}>{ARM[trial.arm]}</span> · Task {trial.task}</p>
        <h2>{trial.question ?? `Task ${trial.task}`}</h2></div>
      <span className={`ws-pill ${trial.state}`}>{trial.state === 'running' ? 'Agent working' : trial.state.replaceAll('_', ' ')}</span>
    </header>
    <div className="ws-agent-body">
      <figure className="ws-browser">
        <div className="frame">
          <div className="frame-bar"><span className="frame-dots"><i /><i /><i /></span><span className="frame-url">ironbark-hire{shown?.path ?? ''}</span><span>{shown ? `Step ${shown.step}` : 'Starting'}</span></div>
          <div className="frame-shot">{shot ? <img src={shot} alt={`Browser at step ${shown!.step}: ${shown!.path ?? 'page'}`} /> : <div className="ws-noshot">{live && !steps.length ? 'Starting a fresh browser…' : 'No screenshot for this step'}</div>}</div>
        </div>
        <figcaption>{scripted ? 'Real jailed browser · scripted rehearsal agent (not a model)' : 'Real jailed browser · screenshot captured by the agent harness'}</figcaption>
        {memory && <p className="ws-memory"><b>Agent memory at step {shown!.step}</b>“{memory}”</p>}
        {answer && <p className="ws-answer"><b>Final answer:</b> {answer}</p>}
      </figure>
      <div className="agent-steps ws-steps-list">
        <p className="ws-steps-head"><span><strong>{steps.length}</strong> steps{trial.current && live ? ' · observing next page' : ''}</span>{picked !== null && <button className="ws-link" onClick={() => setPicked(null)}>{live ? 'Follow live' : 'Latest'}</button>}</p>
        <ol ref={list} aria-label="Agent steps">{steps.map(s => <li key={s.step}><button aria-current={shown?.step === s.step ? 'step' : undefined} onClick={() => setPicked(s.step)}>
          <span className="ws-step-n">{String(s.step).padStart(2, '0')}</span>
          <span className="ws-step-body">
            {s.actions.map((a, i) => <span key={i} className={`ws-action${a.name === 'Answer' ? ' answer' : ''}`}><i aria-hidden="true">{ICON[a.name] ?? '•'}</i>{a.name}{a.target && <em>{a.target}</em>}</span>)}
            {s.goal && <small><b>{scripted ? 'Script' : 'Goal'}:</b> {s.goal}</small>}
            {s.assessment && <small className="ws-assess"><b>Assessed:</b> {s.assessment}</small>}
            {s.error && <small className="ws-error">⚠ {s.error}</small>}
            {s.path && <small className="ws-path">on {s.path}</small>}
          </span></button></li>)}
          {live && trial.state === 'running' && <li className="ws-thinking" aria-live="polite"><span className="ws-step-n">··</span><span>{scripted ? 'Next scripted step…' : 'Muse Spark is deciding the next action…'}</span></li>}
        </ol>
        {trial.errors.length > 0 && <p className="ws-error">{trial.errors.join(' · ')}</p>}
      </div>
    </div>
  </section>;
}

async function get<T>(url: string): Promise<T> { const r = await fetch(url, { cache: 'no-store' }); if (!r.ok) throw new Error('unavailable'); return await r.json() as T; }

/** Follows the trial being executed now; or shows a selected trial (polled while it runs). */
export function AgentPanel({ jobId, active, selection, scripted, onClear }: { jobId: string; active: boolean; selection: Selection | null; scripted: boolean; onClear: () => void }) {
  const [trial, setTrial] = useState<Trial | null>(null);
  const [missing, setMissing] = useState(false);
  useEffect(() => {
    let stop = false;
    const url = selection ? `/api/ironbark/jobs/${jobId}/repetitions/${selection.repetition}/trials/${selection.arm}/${selection.task}` : `/api/ironbark/jobs/${jobId}/live`;
    const load = () => get<Trial | { active: boolean; trial: Trial | null }>(url).then(d => {
      if (stop) return;
      const t = selection ? d as Trial : (d as { trial: Trial | null }).trial;
      setTrial(t); setMissing(!t);
    }).catch(() => { if (!stop) setMissing(true); });
    void load();
    const timer = active ? setInterval(load, 2000) : undefined;
    return () => { stop = true; if (timer) clearInterval(timer); };
  }, [jobId, active, selection?.repetition, selection?.arm, selection?.task]);
  if (!trial) return <div className="ws-empty-note"><p>{missing ? (active ? 'Waiting for the first agent to open a browser…' : 'No agent activity was recorded for this selection.') : 'Loading agent activity…'}</p></div>;
  return <>{selection && <button className="ws-link ws-back" onClick={onClear}>{active ? '← Follow the live agent' : '← Latest run'}</button>}
    <TrialView jobId={jobId} trial={trial} live={active && !selection ? true : active && trial.state === 'running'} scripted={scripted} /></>;
}
