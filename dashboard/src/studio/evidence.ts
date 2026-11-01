import { parseInvestigation } from '../lib/investigation';

export interface ReplayEvent { ref: string; number: number | null; category: string; text: string; ok: boolean | null }
export interface ReplayReport {
  id: string; label: string; provenance: string; recorded: boolean;
  tasks: { id: string; question: string }[];
  sequence: { task: string; arm: string; events: ReplayEvent[]; strict: boolean | null; supported: boolean | null; note: string | null } | null;
  proposals: { label: string; ownerSelected: boolean; validation: string }[];
  verdicts: string[];
}
const bool = (v: unknown) => typeof v === 'boolean' ? v : null;
/** Project only allowlisted public fields; never expose a raw report or trace to the canvas. */
export function adaptReplay(text: string): ReplayReport {
  const parsed = parseInvestigation(text);
  if (!parsed.ok) throw new Error(parsed.error);
  const d = parsed.data;
  if (d.audience !== 'public-demo') throw new Error('Select an already reviewed public-demo export. Private reports are not supported by this studio.');
  if (!d.tasks.every(t => typeof t?.task_id === 'string' && typeof t.question === 'string') || new Set(d.tasks.map(t=>t.task_id)).size !== d.tasks.length) throw new Error('Invalid task context.');
  const recorded = !d.synthetic && d.evidence_origin?.provider === 'real_model' && d.evidence_origin?.presentation === 'recorded';
  const story = d.storyboard;
  if (story && (!Array.isArray(story.steps) || !d.tasks.some(t=>t.task_id===story.task_id) || typeof story.arm!=='string')) throw new Error('Invalid public event sequence.');
  const sequence = recorded && story ? {
    task: story.task_id, arm: story.arm,
    events: story.steps.map((step,i) => {
      if (!step || typeof step.text !== 'string') throw new Error('Archived event text is missing.');
      return { ref: `/storyboard/steps/${i}`, number: typeof step.event==='number' && Number.isFinite(step.event) ? step.event : null,
        category: typeof step.category==='string' ? step.category : 'recorded event', text: step.text, ok: bool(step.ok) };
    }), strict: bool(story.strict_pass), supported: bool(story.evidence_supported), note: typeof story.note==='string' ? story.note : null
  } : null;
  return { id:d.run.id, label:typeof d.demo_case?.label==='string' ? d.demo_case.label : `Report ${d.run.id}`, recorded,
    provenance:recorded ? 'Recorded real-model evidence' : d.evidence_origin?.provider==='dev_fixture' || d.synthetic ? 'Development / synthetic evidence · not a real-model recording' : 'Provenance unverified · replay unavailable',
    tasks:d.tasks.map(t=>({id:t.task_id,question:t.question})), sequence,
    proposals:d.proposals.map(p=>({label:typeof p.label==='string'?p.label:'Proposal label unavailable',ownerSelected:p.owner_selected===true,validation:typeof p.validation==='string'?p.validation:'Unavailable'})),
    verdicts:(d.evaluation.results ?? []).map<string>(v=>v.verdict).concat(d.evaluation.exploratory ? [`Exploratory: ${d.evaluation.exploratory.verdict}`] : []) };
}
