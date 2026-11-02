import { useMemo, useState } from 'react';
import { ACTION_GLYPH, evidence, frame, isItemPage, ITEMS, row, type Trial } from '../evidence';
import { Track, scrollToProgress } from './engine';

/** Editorial notes are ours and are labelled as such; everything else on screen is recorded. */
export type Notes = Record<number, string>;

export function Journey({ id, trial, notes, reduce, title, kicker }: { id: string; trial: Trial; notes: Notes; reduce: boolean; title: string; kicker: string }) {
  const steps = trial.steps;
  const n = steps.length;
  const [index, setIndex] = useState(0);
  const limit = evidence.tasks.find(t => t.task === trial.task)!.limits.max_steps;
  const arm = trial.arm === 'original' ? 'Original' : 'Modified';
  const r = row(arm, trial.task);
  const passed = r.outcome === 'evidence_supported_pass';
  const s = steps[index];
  const opened = useMemo(() => steps.slice(0, index + 1).filter(x => isItemPage(x.path)).length, [steps, index]);
  const frames = useMemo(() => [...new Set(steps.map(x => x.frame).filter(Boolean))] as string[], [steps]);
  const done = s.done;
  // Scroll span: the first 6% settles the stage, then each step owns an equal slice.
  const toIndex = (p: number) => Math.min(n - 1, Math.max(0, Math.floor(((p - .06) / .9) * n)));
  const go = (i: number) => {
    if (reduce) { setIndex(i); return; }
    const el = document.getElementById(id);
    if (el) scrollToProgress(el, .06 + (.9 * (i + .5)) / n, true);
  };

  return <>
    <Track id={id} vh={60 + n * 55} reduce={reduce} label={`${arm} site: the agent's recorded journey`} className={`journey journey-${trial.arm}`}
      onProgress={p => { const i = toIndex(p); setIndex(prev => prev === i ? prev : i); }}
      vars={p => ({ enter: Math.min(1, p / .06) })}>
      <div className="j-wrap">
        <header className="j-head">
          <p className="eyebrow"><span className={`swatch ${trial.arm === 'original' ? 'o' : 'm'}`} aria-hidden="true" />{kicker}</p>
          <h2 className="j-title">{title}</h2>
        </header>
        <div className="j-body">
          <figure className="j-figure">
            <div className="frame">
              <div className="frame-bar"><span className="frame-dots"><i /><i /><i /></span><span className="frame-url">ironbark-hire{s.path}</span><span className="j-site">{arm}</span></div>
              <div className="frame-shot">
                {frames.map(f => <img key={f} src={frame(f)} alt="" aria-hidden={f !== s.frame} className={f === s.frame ? 'on' : ''} loading="lazy" decoding="async" />)}
                <span className="sr-only">{`Recorded screenshot at step ${s.step}, page ${s.path}.`}</span>
              </div>
            </div>
            <figcaption className="figcap"><b>Recorded</b><span>Screenshot the agent saw at step {s.step} · {arm} site · Muse Spark 1.3</span></figcaption>
          </figure>

          <div className={`j-panel${done ? ' done' : ''}`} aria-live={reduce ? 'polite' : 'off'}>
            <div className="j-count"><span className="j-step">{String(s.step).padStart(2, '0')}</span><span className="j-of">/ {String(n).padStart(2, '0')}</span><span className="j-count-label">step</span></div>
            <ul className="j-actions">{s.actions.map((a, i) => <li key={i} className={a.name === 'Answer' ? 'answer' : ''}><i aria-hidden="true">{ACTION_GLYPH[a.name] ?? '•'}</i><span>{a.name}</span>{a.target && <code>{a.target}</code>}</li>)}</ul>
            {done && <p className={`j-verdict ${passed ? 'pass' : 'fail'}`}><strong>{passed ? '✓ Evidence-supported pass' : '✕ Not passed'}</strong><span>Graded independently against ground truth · {r.requests} model requests · {Math.round(r.elapsed_seconds)} s</span></p>}
            {s.goal && !done && <p className="j-goal"><span className="eyebrow">Stated goal</span>{s.goal}</p>}
            {s.memory && <blockquote className="j-memory"><span className="eyebrow">Working memory</span>“{s.memory}”</blockquote>}
            {notes[s.step] && <p className="j-note"><span className="eyebrow">Note</span>{notes[s.step]}</p>}
          </div>
        </div>

        <footer className="j-foot">
          <div className="j-meters">
            <div className="j-meter"><span className="eyebrow">Item pages opened</span>
              <span className="j-items" aria-label={`${opened} of ${ITEMS}`}>{Array.from({ length: ITEMS }, (_, i) => <i key={i} className={i < opened ? 'on' : ''} />)}</span>
              <strong>{opened}<small> / {ITEMS}</small></strong></div>
            <div className="j-meter"><span className="eyebrow">Step limit</span>
              <span className="j-budget"><i style={{ width: `${100 * s.step / limit}%` }} /></span>
              <strong>{s.step}<small> / {limit}</small></strong></div>
          </div>
          <nav className="j-ticks" aria-label={`${arm} journey steps`}>
            {steps.map((x, i) => <button key={x.step} className={`${isItemPage(x.path) ? 'item' : ''}${x.done ? ' done' : ''}`} aria-current={i === index ? 'step' : undefined}
              aria-label={`Step ${x.step}: ${x.actions.map(a => a.name).join(', ')} on ${x.path}`} onClick={() => go(i)}><span>{x.step}</span></button>)}
          </nav>
          {reduce && <div className="j-stepper"><button className="btn btn-ghost btn-sm" disabled={index === 0} onClick={() => setIndex(i => i - 1)}>← Previous step</button><button className="btn btn-sm" disabled={index === n - 1} onClick={() => setIndex(i => i + 1)}>Next step →</button></div>}
        </footer>
      </div>
    </Track>
    <details className="wrap transcript">
      <summary>Full recorded transcript · {arm} · {n} steps</summary>
      <ol>{steps.map(x => <li key={x.step}><span className="mono">{String(x.step).padStart(2, '0')}</span><div>
        <p><strong>{x.actions.map(a => a.target ? `${a.name}: ${a.target}` : a.name).join(' · ')}</strong> <span className="mono muted">on {x.path}</span></p>
        {x.goal && <p>Goal: {x.goal}</p>}{x.memory && <p className="muted">Memory: {x.memory}</p>}</div></li>)}</ol>
    </details>
  </>;
}
