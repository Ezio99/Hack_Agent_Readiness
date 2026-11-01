import { useEffect, useState } from 'react';
import { Transformation } from './Transformation';
import recording from '../fixtures/ironbark-s1-recorded.json';
import { adaptReplay, type ReplayReport } from './evidence';
import fontLicense from './assets/OFL.txt?url';
import './studio.css';
const INITIAL = adaptReplay(JSON.stringify(recording));
const PACE_MS = 2200; // Editorial presentation interval, never an archived duration.
const stages = ['Scan','Insights','Improvements','Results'] as const;
const mark = <svg viewBox="0 0 48 48" fill="none" aria-hidden="true"><path d="M10 34V16h13M23 34h15V16M10 34l28-18" stroke="currentColor" strokeWidth="3" strokeLinecap="round"/><circle cx="10" cy="34" r="4" fill="currentColor"/><circle cx="38" cy="16" r="4" fill="currentColor"/></svg>;
export function ReplayStudio({openReport}:{openReport:()=>void}) {
  const [report,setReport]=useState(INITIAL),[imported,setImported]=useState<ReplayReport|null>(null),[error,setError]=useState('');
  const [version,setVersion]=useState(0);
  const [task,setTask]=useState(INITIAL.sequence?.task ?? INITIAL.tasks[0]?.id ?? ''),[stage,setStage]=useState<typeof stages[number]>('Insights');
  const choose=(d:ReplayReport)=>{setVersion(v=>v+1);setReport(d);setTask(d.sequence?.task ?? d.tasks[0]?.id ?? '');setError('');};
  return <div className="replay-studio"><a className="studio-skip" href="#studio-main">Skip to replay</a>
    <header className="studio-header"><a href="#/studio" className="studio-brand"><span>{mark}</span>Agent Readiness<small>REPLAY STUDIO</small></a><button onClick={openReport}>Classic dashboard ↗</button></header>
    <div className="studio-toolbar"><label>Report<select aria-label="Report" value={report===INITIAL?'built-in':'imported'} onChange={e=>choose(e.target.value==='built-in'?INITIAL:imported!)}><option value="built-in">{INITIAL.label}</option>{imported && <option value="imported">{imported.label}</option>}</select></label>
      <label>Task<select aria-label="Task" value={task} onChange={e=>setTask(e.target.value)}>{report.tasks.map(t=><option key={t.id} value={t.id}>{t.question}</option>)}</select></label>
    </div>
    <nav aria-label="Product stages" className="studio-stages">{stages.map((s,i)=><button key={s} aria-current={stage===s?'step':undefined} onClick={()=>setStage(s)}><span>0{i+1}</span>{s}</button>)}</nav>
    <main id="studio-main" tabIndex={-1}>
      <div className="studio-player" hidden={stage!=='Insights'}><Player key={`${version}-${task}`} report={report} task={task} active={stage==='Insights'} inspectChange={()=>setStage('Improvements')}/></div>
      {stage==='Insights'?null:stage==='Improvements'?<Transformation available={report===INITIAL} returnToReplay={()=>setStage('Insights')}/>:<section className="studio-context"><p className="studio-kicker">{stage}</p><h1>{stage==='Scan'?'Start with a recorded task.':'Keep the verdict in view.'}</h1>
        {stage==='Scan'?<><p>{report.label}</p><p>{report.provenance}. Select a task above, then open Insights to inspect its archived journey.</p><button onClick={()=>setStage('Insights')}>Open agent journey →</button></>:<><p>Stored verdicts: {report.verdicts.join(' · ') || 'Unavailable'}</p><p>Run-specific observations do not establish general website improvement. Interactive results are a future checkpoint.</p><button onClick={openReport}>Choose report in classic dashboard →</button></>}
      </section>}
    </main>
    <details className="studio-import"><summary>Report sources & technical details</summary><p>{report.provenance}. Playback is local and requires no inference. Reports are explicitly selected; no outcome-based ranking is used. The classic dashboard has its own report selection.</p><label>Load a reviewed public report<input type="file" accept=".json,application/json" onChange={async e=>{const file=e.target.files?.[0];e.target.value='';if(!file)return;if(file.size>2_000_000){setError('Report exceeds 2 MB.');return;}try{const d=adaptReplay(await file.text());setImported(d);choose(d);}catch(err){setError(err instanceof Error?err.message:'Unable to read report');}}}/></label>{error&&<p role="alert">{error}</p>}<p>The current adapter reads the existing public storyboard contract, independent of trial counts. Richer trace formats need a reviewed adapter; raw traces and private reports are rejected. Imported reports stay in memory for this tab.</p><a href={fontLicense}>Geist font license</a></details>
  </div>;
}
function Player({report,task,active,inspectChange}:{report:ReplayReport;task:string;active:boolean;inspectChange:()=>void}) {
  const seq=report.sequence?.task===task?report.sequence:null;
  const events=seq?.events??[];
  const [index,setIndex]=useState(0),[playing,setPlaying]=useState(false);
  useEffect(()=>{if(!active)setPlaying(false);},[active]);
  const current=events[index],question=report.tasks.find(t=>t.id===task)?.question ?? 'No task available';
  const select=(next:number)=>{setPlaying(false);setIndex(Math.max(0,Math.min(events.length-1,next)));};
  useEffect(()=>{if(!playing)return;const timer=setTimeout(()=>{if(index>=events.length-1)setPlaying(false);else { setIndex(i=>i+1); if(index===events.length-2)setPlaying(false); }},PACE_MS);return()=>clearTimeout(timer);},[playing,index,events.length]);
  useEffect(()=>{const pause=()=>{if(document.hidden)setPlaying(false);};document.addEventListener('visibilitychange',pause);return()=>document.removeEventListener('visibilitychange',pause);},[]);
  const progress=events.length?`${index+1} / ${events.length}`:'No events';
  const isTool=current?.category==='browser tool';
  return <><div className="studio-title"><div><p className="studio-kicker">OBSERVE THE AGENT</p><h1>See the journey. Find the friction.</h1></div><span className="studio-recorded">{report.provenance}</span></div>
    <div className="studio-workspace"><section className="studio-canvas" aria-label="Agent replay canvas"><div className="canvas-chrome"><span>● ● ●</span><span>Event visualization · No page reconstruction</span><span>{seq?.arm ?? '—'}</span></div><div className="canvas-task"><span className="studio-kicker">SELECTED TASK</span><h2>{question}</h2></div>
      {current?<div key={current.ref} className={`studio-action ${isTool?'tool-action':''}`} data-event-ref={current.ref}><div className="action-top"><span>{current.category}</span><span>Archive event {current.number??'unavailable'}</span></div><div className="studio-action-symbol" aria-hidden="true">{isTool?'↧':current.category==='page observation'?'◉':'↗'}</div><h3>{current.text}</h3><p>Recorded event · Exact archived text</p></div>:<div className="studio-empty"><h3>Public replay unavailable</h3><p>This task has no supported archived event sequence in the selected report. No substitute journey is shown.</p></div>}
      <div className="canvas-caption">{isTool?'Browser-tool behavior · Not a verified website defect':'Composed event view · No fabricated cursor path, page contents or reasoning'}</div>
    </section>
    <aside className="studio-inspector" aria-label="Evidence inspector"><div className="inspector-heading"><span className="studio-kicker">EVIDENCE INSPECTOR</span><span aria-live="polite">{progress}</span></div><h2>{current?.category ?? 'No selected event'}</h2><dl><dt>Recorded action / observation</dt><dd>{current?.text ?? 'Unavailable'}</dd><dt>Tool / browser behavior</dt><dd>{isTool?current.text:'No additional tool detail in this public event.'}</dd><dt>Event status</dt><dd>{current?.ok===true?'Recorded OK':current?.ok===false?'Recorded not OK':'Unavailable'}</dd><dt>Task outcome</dt><dd className={seq?.supported===true?"studio-supported":undefined}>{seq?`Strict: ${seq.strict===true?'pass':seq.strict===false?'fail':'unavailable'} · Evidence-supported: ${seq.supported===true?'pass':seq.supported===false?'fail':'unavailable'}`:'Unavailable for this selection'}</dd></dl><details><summary>Source & interpretation</summary><p>Source: <code>{current?.ref ?? 'Unavailable'}</code></p><p>Task: {task} · Arm: {seq?.arm??'unavailable'}</p><p>{seq?.note}</p><p>The canvas is a presentation of archived text, not a browser recording. No causal website diagnosis is inferred from these events.</p></details></aside></div>
    <section className="studio-playback" aria-label="Replay controls"><div className="transport"><div><button disabled={!events.length} onClick={()=>select(0)} aria-label="Restart replay">↺</button><button disabled={!events.length||index===0} onClick={()=>select(index-1)} aria-label="Previous event">←</button><button className="play-control" disabled={!events.length||(!playing&&index===events.length-1)} onClick={()=>setPlaying(v=>!v)}>{playing?'Pause':'Play'}</button><button disabled={!events.length||index===events.length-1} onClick={()=>select(index+1)} aria-label="Next event">→</button></div><span>Step {progress}</span><button onClick={inspectChange}>Inspect listing change →</button><small>Presentation pacing · {PACE_MS/1000}s per entry, not recorded timing</small></div>
    <input aria-label="Replay position" type="range" min="0" max={Math.max(0,events.length-1)} value={index} disabled={!events.length} onChange={e=>select(Number(e.target.value))} aria-valuetext={current?`Step ${index+1}: ${current.text}`:'No archived events'}/>
    <ol className="studio-events" aria-label="Archived events">{events.map((event,i)=><li key={event.ref}><button aria-current={i===index?'step':undefined} onClick={()=>select(i)} title={event.text}><span>{String(i+1).padStart(2,'0')}</span><strong>{event.category}</strong><small>{event.text}</small></button></li>)}</ol></section></>;
}
