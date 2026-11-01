// @vitest-environment jsdom
import {act} from 'react';
import {createRoot, type Root} from 'react-dom/client';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {ReplayStudio} from './ReplayStudio';
import {adaptReplay} from './evidence';
import App from '../App';
import {Tasks} from './Tasks';
import {ArchivedResults,summarizeArchivedS1} from './ArchivedResults';
import {Transformation,transformationReference} from './Transformation';
import {createHash} from 'node:crypto';
import {readFileSync} from 'node:fs';
import recording from '../fixtures/ironbark-s1-recorded.json';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT=true;
let host:HTMLDivElement,root:Root;
beforeEach(()=>{host=document.createElement('div');document.body.append(host);root=createRoot(host);});
afterEach(()=>{act(()=>root.unmount());host.remove();vi.useRealTimers();});
const mount=()=>act(()=>root.render(<ReplayStudio openReport={()=>{}}/>));
const click=(label:string)=>act(()=>{const b=[...host.querySelectorAll('button')].find(b=>b.getAttribute('aria-label')===label||b.textContent?.endsWith(label));expect(b).toBeTruthy();b!.click();});
const position=()=>host.querySelector('.studio-action')?.getAttribute('data-event-ref');
it('studio is the default, with full-report fallback navigation',()=>{window.location.hash='';act(()=>root.render(<App/>));expect(host.textContent).toContain('See the journey.');click('Classic dashboard ↗');expect(window.location.hash).toBe('#/investigation');});
it('steps, event selection, scrub and inspector refer to the same archived entry',()=>{
 mount();const events=recording.storyboard.steps;
 expect(position()).toBe('/storyboard/steps/0');expect([...host.querySelectorAll('button')].some(b=>b.textContent==='Pause')).toBe(false);
 click('Next event');expect(position()).toBe('/storyboard/steps/1');expect(host.querySelector('.studio-inspector')?.textContent).toContain(events[1].text);
 click('Previous event');expect(position()).toBe('/storyboard/steps/0');
 act(()=>{(host.querySelectorAll('.studio-events button')[7] as HTMLButtonElement).click();});expect(position()).toBe('/storyboard/steps/7');
 const input=host.querySelector('input[type=range]') as HTMLInputElement;
 act(()=>{Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value')!.set!.call(input,'4');input.dispatchEvent(new Event('change',{bubbles:true}));input.dispatchEvent(new Event('input',{bubbles:true}));});
 expect(position()).toBe('/storyboard/steps/4');click('Restart replay');expect(position()).toBe('/storyboard/steps/0');
});
it('play, pause and restart use fixed presentation pacing and stop at the end',()=>{
 vi.useFakeTimers();mount();click('Play');act(()=>vi.advanceTimersByTime(2200));expect(position()).toBe('/storyboard/steps/1');click('Pause');act(()=>vi.advanceTimersByTime(5000));expect(position()).toBe('/storyboard/steps/1');click('Restart replay');click('Play');
 for(let i=0;i<recording.storyboard.steps.length-1;i++)act(()=>vi.advanceTimersByTime(2200));
 expect(position()).toBe(`/storyboard/steps/${recording.storyboard.steps.length-1}`);expect([...host.querySelectorAll('button')].some(b=>b.textContent==='Pause')).toBe(false);expect(host.querySelector('.transport')?.textContent).toContain('Illustrative timing');
});
it('selecting a task with no archive stops playback and shows no borrowed events',()=>{
 vi.useFakeTimers();mount();click('Play');const select=host.querySelectorAll('select')[1];
 act(()=>{select.value=recording.tasks[1].task_id;select.dispatchEvent(new Event('change',{bubbles:true}));});act(()=>vi.advanceTimersByTime(5000));
 expect(host.textContent).toContain('Public replay unavailable');expect(host.querySelectorAll('.studio-events button')).toHaveLength(0);expect(position()).toBeUndefined();
});
it('adapter is independent of trial structure and preserves duplicate event references, optional statuses and verdicts',()=>{
 const d=structuredClone(recording) as any;d.tasks[0].patched={};delete d.storyboard.steps[0].ok;delete d.storyboard.strict_pass;
 const adapted=adaptReplay(JSON.stringify(d));expect(adapted.sequence?.strict).toBeNull();expect(adapted.sequence?.events[0].ok).toBeNull();expect(adapted.sequence?.events.map(e=>e.ref)).toHaveLength(d.storyboard.steps.length);expect(adapted.verdicts).toContain('inconclusive');expect(adapted.verdicts).toContain('Exploratory: not_supported');
 d.storyboard.steps=d.storyboard.steps.slice(0,1);expect(adaptReplay(JSON.stringify(d)).sequence?.events).toHaveLength(1);
 delete d.storyboard;expect(adaptReplay(JSON.stringify(d)).sequence).toBeNull();
});
it('never labels development or unknown provenance as a real-model replay',()=>{
 const d=structuredClone(recording) as any;d.evidence_origin.provider='dev_fixture';expect(adaptReplay(JSON.stringify(d)).sequence).toBeNull();expect(adaptReplay(JSON.stringify(d)).provenance).toContain('not a real-model');delete d.evidence_origin;expect(adaptReplay(JSON.stringify(d)).provenance).toContain('unverified');
});
it('rejects private/raw data and excludes unselected payload fields from projected evidence',()=>{
 const d=structuredClone(recording) as any;d.audience='private';expect(()=>adaptReplay(JSON.stringify(d))).toThrow('public-demo');d.audience='public-demo';d.raw_trace='SECRET';expect(()=>adaptReplay(JSON.stringify(d))).toThrow();delete d.raw_trace;d.unknown_payload='DO_NOT_PROJECT';expect(JSON.stringify(adaptReplay(JSON.stringify(d)))).not.toContain('DO_NOT_PROJECT');d.storyboard.steps[0].text=null;expect(()=>adaptReplay(JSON.stringify(d))).toThrow('text is missing');
});
it('shows owner-selection and stored verdicts with the static archived Results summary',()=>{mount();click('Improvements');expect(host.textContent).toContain('Owner-selected · Not independently verified');click('Results');expect(host.textContent).toContain('inconclusive');expect(host.textContent).toContain('not_supported');expect(host.textContent).toContain('Static archived summary');});

it('transformation preserves replay position, pauses on exit, and separates illustration from evidence',()=>{
 vi.useFakeTimers();mount();click('Next event');click('Play');click('Inspect listing change →');
 expect(host.querySelector('.illustration-notice')?.textContent).toBe('Illustrative transformation — not recorded browser footage.');
 expect(host.querySelectorAll('.surfaced-fields>div')).toHaveLength(3);
 expect(host.querySelector('.transformation')?.textContent).toContain('No product values shown');
 click('Focus proposed layout');expect(host.querySelector('.focus-proposed')).not.toBeNull();click('Show both layouts');
 act(()=>vi.advanceTimersByTime(5000));click('Return to agent journey');expect(position()).toBe('/storyboard/steps/1');expect([...host.querySelectorAll('button')].some(b=>b.textContent==='Pause')).toBe(false);
 click('Next event');expect(position()).toBe('/storyboard/steps/2');click('Restart replay');expect(position()).toBe('/storyboard/steps/0');
});
it('S1 illustration is source-pinned, preserves separate derived outcomes, and is unavailable for other reports',()=>{
 expect(createHash('sha256').update(readFileSync('src/fixtures/ironbark-s1-recorded.json')).digest('hex')).toBe(transformationReference.sha256);
 act(()=>root.render(<Transformation available={true} returnToReplay={()=>{}}/>));
 expect(host.querySelector('.transformation-evidence')?.textContent).toContain('original 2/4 versus modified 3/4');
 expect(host.querySelector('.transformation-evidence')?.textContent).toContain('50 versus 29');
 expect(host.textContent).toContain('Website improvement not established');
 act(()=>root.render(<Transformation available={false} returnToReplay={()=>{}}/>));expect(host.textContent).toContain('No reviewed transformation');expect(host.querySelector('.transformation-layouts')).toBeNull();
});

it('Results shows contemporary aggregates, both arm labels, original verdicts and no established improvement',()=>{
 mount();click('Results');const summary=host.querySelector('.archived-results')!;
 expect([...summary.querySelectorAll('dt')].map(n=>n.textContent)).toEqual(['Original','Modified','Original','Modified']);
 expect(summary.querySelector('.results-impact')?.textContent).toContain('+1additional task passed');expect(summary.querySelector('.results-impact')?.textContent).toContain('42%fewer agent requests');
 const details=summary.querySelector('details')!;expect(details.open).toBe(false);expect(details.querySelector('summary')?.textContent).toBe('Technical details');expect(details.textContent).toContain('Original is the contemporary placebo arm');
 expect([...summary.querySelectorAll('dd')].map(n=>n.textContent)).toEqual(['2/4','3/4','50','29']);
 expect(summary.textContent).toContain('inconclusive');expect(summary.textContent).toContain('not_supported');expect(summary.textContent).toContain('Website improvement was not established.');expect(summary.textContent).toContain('Not an independently verified recommendation');expect(summary.textContent).toContain('not scores for the selected task');
});
it('Results never borrows S1 values for unsupported report/task selections',()=>{
 for(const props of [{available:false,task:recording.tasks[0].task_id},{available:true,task:'unknown-task'}]){
 act(()=>root.render(<ArchivedResults {...props} openReport={()=>{}}/>));expect(host.textContent).toContain('Archived results unavailable');expect(host.querySelector('.results-comparison')).toBeNull();
 }
});
it('aggregate adapter rejects missing/void/repeated/unsupported rows and ignores historical trials',()=>{
 const task=recording.tasks[1].task_id;
 const d=structuredClone(recording) as any;d.tasks.forEach((t:any)=>t.baseline.forEach((r:any)=>{r.passed=true;r.evidence_backed=true;r.model_requests=99999;}));
 expect(summarizeArchivedS1(d,task)?.original).toEqual({supported:2,total:4,requests:50});expect(summarizeArchivedS1(d,task)?.modified.requests).toBe(29);
 for(const edit of [(x:any)=>delete x.tasks[0].patched['change-1'],(x:any)=>x.tasks[0].placebo['change-1'][0].void=true,(x:any)=>x.tasks[0].patched['change-1'].push(x.tasks[0].patched['change-1'][0]),(x:any)=>delete x.tasks[0].patched['change-1'][0].model_requests,(x:any)=>x.evidence_origin.provider='dev_fixture']){
 const source=structuredClone(recording) as any;edit(source);expect(summarizeArchivedS1(source,task)).toBeNull();
 }
});

it('Scan describes the archived case and opens the existing journey',()=>{mount();click('Scan');const scan=host.querySelector('.studio-scan')!;expect(scan.textContent).toContain('not a live scan');expect(scan.textContent).toContain('Ironbark Hire Co.');expect(scan.textContent).toContain('4 recorded tasks');expect(scan.textContent).toContain('Meta Muse Spark 1.3');click('Explore agent journey →');expect(position()).toBe('/storyboard/steps/0');});

it('repetitive scrolls have distinct selected entries without rewriting their archived text',()=>{mount();for(const i of [2,3,4]){act(()=>{(host.querySelectorAll('.studio-events button')[i] as HTMLButtonElement).click();});expect(host.querySelector('.replay-state')?.textContent).toContain(`Entry ${i+1} of 9`);expect(host.querySelector('.studio-action h3')?.textContent).toBe('Scrolled');expect(host.querySelector('.action-top')?.textContent).toContain(`Entry ${String(i+1).padStart(2,'0')}`);expect(host.querySelector('.studio-inspector')?.textContent).toContain('Scrolled');}act(()=>{(host.querySelectorAll('.studio-events button')[5] as HTMLButtonElement).click();});expect(host.querySelector('.tool-action')?.textContent).toContain('Missing scroll index');expect(host.querySelector('.scroll-evidence-note')).toBeNull();});

it('Tasks preserves exact safe prompts, owner provenance, and replay/event continuity',()=>{mount();click('Next event');click('Tasks');expect(host.querySelector('.studio-tasks')?.textContent).toContain('These prompts were not model-generated');expect([...host.querySelectorAll('.task-list strong')].map(n=>n.textContent)).toEqual(recording.tasks.map(t=>t.question));click('Explore recorded journey →');expect(position()).toBe('/storyboard/steps/1');click('Tasks');act(()=>{(host.querySelectorAll('.task-list button')[1] as HTMLButtonElement).click();});expect(host.querySelector('.task-detail h2')?.textContent).toBe(recording.tasks[1].question);expect(host.querySelector('.task-detail')?.textContent).toContain('Replay unavailable');expect(host.querySelector('.task-detail button')).toBeNull();expect((host.querySelectorAll('select')[1] as HTMLSelectElement).value).toBe(recording.tasks[1].task_id);});
it('Tasks does not infer imported generation provenance or expose extra payload fields',()=>{const report=adaptReplay(JSON.stringify(recording));act(()=>root.render(<Tasks report={report} task={report.tasks[0].id} selectTask={()=>{}} openJourney={()=>{}} reviewedS1={false}/>));expect(host.textContent).toContain('Generation, selection and freeze provenance are unavailable');expect(host.textContent).not.toContain('Owner-authored · Recorded');expect(host.querySelector('textarea')).toBeNull();});

it('technical identifiers and exact pace are disclosed without obscuring selected event context',()=>{mount();expect(host.querySelector('.transport')?.textContent).toContain('Illustrative timing');expect(host.querySelector('.transport')?.textContent).not.toContain('2.2');expect(host.querySelector('.action-top')?.textContent).not.toContain('Archive event');const details=host.querySelector('.event-technical') as HTMLDetailsElement;expect(details.open).toBe(false);expect(details.textContent).toContain('Archive event: 9');expect(details.textContent).toContain('2.2 seconds');expect(details.textContent).toContain('/storyboard/steps/0');expect(host.querySelector('.replay-state')?.textContent).toContain('Entry 1 of 9');});
