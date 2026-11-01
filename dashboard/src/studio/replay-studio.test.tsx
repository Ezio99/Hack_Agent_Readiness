// @vitest-environment jsdom
import {act} from 'react';
import {createRoot, type Root} from 'react-dom/client';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {ReplayStudio} from './ReplayStudio';
import {adaptReplay} from './evidence';
import App from '../App';
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
 expect(position()).toBe('/storyboard/steps/0');expect(host.textContent).not.toContain('Pause');
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
 expect(position()).toBe(`/storyboard/steps/${recording.storyboard.steps.length-1}`);expect(host.textContent).not.toContain('Pause');expect(host.textContent).toContain('not recorded timing');
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
it('shows owner-selection and original verdicts without implementing transformation/results',()=>{mount();click('Improvements');expect(host.textContent).toContain('Owner-selected · Not independently verified');click('Results');expect(host.textContent).toContain('inconclusive');expect(host.textContent).toContain('not_supported');expect(host.textContent).toContain('future checkpoint');});
