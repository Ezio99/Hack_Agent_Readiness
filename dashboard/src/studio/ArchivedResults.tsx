import recording from '../fixtures/ironbark-s1-recorded.json';
import type { InvestigationExport, TrialRow } from '../lib/investigation';

/** Read-only, report-wide contemporary comparison; no historical baseline or regrading. */
export function summarizeArchivedS1(d: InvestigationExport, task: string) {
  if (!d.run.complete || d.evidence_origin?.provider !== 'real_model' || d.evidence_origin.presentation !== 'recorded' || d.synthetic || !d.tasks.length || !d.tasks.some(t=>t.task_id===task)) return null;
  const proposalId=recording.proposals[0].id;
  const proposal=d.proposals.find(p=>p.id===proposalId && p.owner_selected===true);
  const frozen=d.evaluation.results.find(r=>r.proposal_id===proposalId)?.verdict;
  const exploratory=d.evaluation.exploratory?.verdict;
  if(!proposal || !frozen || !exploratory) return null;
  const summarize=(arm:'placebo'|'patched')=>{
    const trials=d.tasks.map(t=>t[arm]?.[proposalId]);
    if(trials.some(rows=>!rows || rows.length!==1)) return null;
    const rows=trials.flat() as TrialRow[];
    if(rows.some(r=>r.void || r.run_status!=='completed' || typeof r.passed!=='boolean' || typeof r.evidence_backed!=='boolean' || !Number.isSafeInteger(r.model_requests) || (r.model_requests??-1)<0)) return null;
    return {supported:rows.filter(r=>r.passed && r.evidence_backed).length, total:rows.length, requests:rows.reduce((sum,r)=>sum+(r.model_requests??0),0)};
  };
  const original=summarize('placebo'),modified=summarize('patched');
  return original && modified ? {original,modified,frozen,exploratory} : null;
}
export function ArchivedResults({available,task,openReport}:{available:boolean;task:string;openReport:()=>void}) {
  const result=available?summarizeArchivedS1(recording as unknown as InvestigationExport,task):null;
  if(!result)return <section className="studio-context"><p className="studio-kicker">RESULTS</p><h1>Archived results unavailable</h1><p>This report/task selection does not have a supported aggregate comparison in this summary. No S1 values are substituted. Choose the built-in reviewed report or use the classic dashboard’s own report selection.</p><button onClick={openReport}>Classic dashboard details ↗</button></section>;
  const additional=result.modified.supported-result.original.supported;
  const fewerRequests=result.original.requests>0?Math.round(100*(result.original.requests-result.modified.requests)/result.original.requests):null;
  return <section className="archived-results" aria-label="Archived S1 results">
    <div className="studio-title"><div><p className="studio-kicker">RECORDED OBSERVATIONS · IRONBARK</p><h1>See what changed.</h1></div><button onClick={openReport}>Classic dashboard details ↗</button></div>
    <p className="results-scope">Original → Modified · Across all {result.original.total} tasks</p>
    <div className="results-comparison results-impact">
      <article><div className="results-impact-number">{additional>0?'+':''}{additional}</div><h2>additional {additional===1?'task':'tasks'} passed</h2><p>Evidence-supported passes</p><dl><div><dt>Original</dt><dd>{result.original.supported}/{result.original.total}</dd></div><span aria-hidden="true">→</span><div><dt>Modified</dt><dd>{result.modified.supported}/{result.modified.total}</dd></div></dl></article>
      <article><div className="results-impact-number">{fewerRequests===null?'—':`${fewerRequests}%`}</div><h2>fewer agent requests</h2><p>Recorded model requests</p><dl><div><dt>Original</dt><dd>{result.original.requests}</dd></div><span aria-hidden="true">→</span><div><dt>Modified</dt><dd>{result.modified.requests}</dd></div></dl></article>
    </div>
    <p className="results-attribution">Owner-selected change · Not an independently verified recommendation</p>
    <details className="transformation-evidence results-technical"><summary>Technical details</summary>
      <div className="results-verdicts"><div><span>Frozen verdict</span><strong>{result.frozen}</strong></div><div><span>Exploratory result</span><strong>{result.exploratory}</strong></div></div>
      <p className="results-qualification">Website improvement was not established.</p>
      <p>Report-wide observations across all {result.original.total} frozen tasks, not scores for the selected task. The descriptive differences do not establish statistical significance, causal proof or generalizability.</p>
      <p>Static archived summary of the Ironbark S1 sensitivity experiment: Original is the contemporary placebo arm; Modified is the patched arm. Values come from the approved public report, not a fresh evaluation. Historical baseline, EXP-C and R1 are excluded.</p>
      <p>The frozen evaluation uses the archived {recording.evaluation.rule.id} rule; the separate exploratory result uses {recording.evaluation.exploratory.rules_id}. Stored verdicts are shown unchanged; grading and decision rules are not rerun. Request reduction is rounded to a whole percent relative to Original.</p>
      <p>This release shows static archived outcomes. Interactive result exploration remains future work. The classic dashboard retains detailed investigation and its separate report selection.</p>
    </details>
  </section>;
}
