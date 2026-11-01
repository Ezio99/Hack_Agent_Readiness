import { useState } from 'react';
import recording from '../fixtures/ironbark-s1-recorded.json';
import { tally, type TrialRow } from '../lib/investigation';
/** Explicit editorial reference, bound only to the built-in reviewed report by the caller. */
export const transformationReference = {
  source: 'ironbark-s1-recorded.json',
  sha256: '87e3b05804ba05b692c15426142e6ec7192ca27f03f0dd4937330db13fd8156f',
  proposal: 'change-1', fields: ['Refundable deposit','Minimum hire','Delivery and collection'],
};
const originalRows=recording.tasks.flatMap(t=>t.placebo[transformationReference.proposal as 'change-1']) as TrialRow[];
const modifiedRows=recording.tasks.flatMap(t=>t.patched[transformationReference.proposal as 'change-1']) as TrialRow[];
const original=tally(originalRows),modified=tally(modifiedRows);
const totalRequests=(rows:TrialRow[])=>rows.some(r=>r.void||typeof r.model_requests!=='number')?'Unavailable':rows.reduce((sum,r)=>sum+(r.model_requests??0),0);
export function Transformation({available,returnToReplay}:{available:boolean;returnToReplay:()=>void}) {
  const [focus,setFocus]=useState(false);
  if(!available)return <section className="studio-context"><h1>No reviewed transformation for this report</h1><p>The existing illustration is bound to the built-in S1 report. Another report needs an explicitly reviewed patch reference; its contents are never inferred.</p><button onClick={returnToReplay}>Return to agent journey</button></section>;
  return <section className="transformation" aria-label="Illustrative website transformation">
    <div className="studio-title"><div><p className="studio-kicker">Owner-selected · Not independently verified</p><h1>Same information. Closer to the decision.</h1></div><button onClick={returnToReplay}>Return to agent journey</button></div>
    <p className="illustration-notice">Illustrative transformation — not recorded browser footage.</p>
    <p className="transformation-intro">Surface existing rental terms on listing cards. This shows the layout idea, not captured pages or a verified effect.</p>
    <button aria-pressed={focus} onClick={()=>setFocus(v=>!v)}>{focus?'Show both layouts':'Focus proposed layout'}</button>
    <div className={`transformation-layouts ${focus?'focus-proposed':''}`}>
      {[false,true].map(after=><article key={String(after)} className={`transformation-browser ${after?'proposed-layout':'original-layout'}`} aria-label={after?'Proposed illustrative layout':'Original illustrative layout'}>
        <header><span aria-hidden="true">● ● ●</span><strong>{after?'Proposed layout':'Original layout'}</strong><small>ILLUSTRATION</small></header>
        <div className="mock-site"><div className="mock-heading">Equipment listings</div><div className="mock-listing"><div className="mock-product"><svg viewBox="0 0 150 80" aria-hidden="true"><path d="M20 56h110l-12-36H55L36 40H20Z M60 20V10h40v10" fill="none" stroke="currentColor" strokeWidth="2"/><circle cx="42" cy="59" r="10"/><circle cx="112" cy="59" r="10"/></svg><h2>Equipment listing</h2></div>
        {after?<div className="surfaced-fields">{transformationReference.fields.map(field=><div key={field}><span>{field}</span><small>Existing field</small></div>)}</div>:<div className="mock-placeholder" aria-hidden="true"><i/><i/></div>}
        </div>
        {!after&&<div className="detail-fields"><h3>Within item details</h3>{transformationReference.fields.map(field=><span key={field}>{field}</span>)}</div>}
        <p className="mock-note">{after?'Terms surfaced on the listing card':'Terms less prominent on the listing'} · No product values shown</p></div>
      </article>)}
    </div>
    <details className="transformation-evidence"><summary>Patch basis & separate experimental outcomes</summary><p>Owner-selected change: copy existing deposit, minimum-hire and delivery terms to listing cards. Source: the reviewed S1 reference, proposal <code>{transformationReference.proposal}</code>. No agent recommendation or causal explanation is inferred.</p><p>Recorded S1 comparison: original {original.supported}/{original.usable} versus modified {modified.supported}/{modified.usable} evidence-supported passes; {totalRequests(originalRows)} versus {totalRequests(modifiedRows)} model requests.</p><p>Website improvement not established. Frozen: {recording.evaluation.results[0].verdict}; exploratory: {recording.evaluation.exploratory.verdict}. These outcomes are separate from this illustration.</p></details>
  </section>;
}
