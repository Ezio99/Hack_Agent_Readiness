// @vitest-environment jsdom
import { act } from 'react';
import { createRoot } from 'react-dom/client';
import { expect, it } from 'vitest';
import { InvestigationPage, provenanceOf } from './pages/Investigation';
import { parseInvestigation, tally, type InvestigationExport } from './lib/investigation';
import recording from './fixtures/ironbark-s1-recorded.json';
(globalThis as any).IS_REACT_ACT_ENVIRONMENT = true;
it('opens recorded S1 with no backend, provenance and contemporary results first; setup stays closed', async () => {
 sessionStorage.clear(); const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
 await act(async()=>{root.render(<InvestigationPage/>);await new Promise(r=>setTimeout(r,200));});
 await act(async()=>{await new Promise(r=>setTimeout(r,100));});
 expect(host.textContent).toContain('Recorded Ironbark S1');
 expect(host.querySelector('.product-outcomes')?.textContent).toContain('Original website2/4evidence-supported passes');
 expect(host.querySelector('.product-outcomes')?.textContent).toContain('Modified website3/4evidence-supported passes');
 expect(host.querySelector('.product-outcomes')?.textContent).toContain('42% fewer');
 expect(host.textContent).toContain('50 → 29');
 expect(host.querySelector('.product-qualification')?.textContent).toBe('Small controlled experiment · Improvement not established.');
 expect(host.querySelector('.experiment-details')?.hasAttribute('open')).toBe(false);
 expect(host.querySelector('[aria-label="Product workflow"]')?.querySelectorAll('button').length).toBe(4);
 expect(host.querySelector('.product-story ol')?.children.length).toBe(9);
 expect(host.querySelector('.suggestion-card')?.textContent).toContain('Owner-selected · Not independently verified');
 expect(host.textContent).not.toContain('only two tasks');
 expect(host.querySelector('.advanced')?.hasAttribute('open')).toBe(false);
 expect(host.querySelector('[aria-label="Recorded agent actions"]')).not.toBeNull();
 expect(host.querySelector('h1')!.compareDocumentPosition(host.querySelector('.advanced')!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
 act(()=>root.unmount());host.remove();
});
it('uses authoritative origin and conservative unknown; separates strict/evidence support',()=>{
 const d=structuredClone(recording) as unknown as InvestigationExport;
 expect(provenanceOf(d).label).toContain('RECORDED REAL-MODEL');
 d.evidence_origin={provider:'dev_fixture',presentation:'recorded'};expect(provenanceOf(d).label).toContain('not a real model');
 delete d.evidence_origin;expect(provenanceOf(d).label).toContain('unverified');
 d.synthetic=true;expect(provenanceOf(d).kind).toBe('synthetic');
 const row=d.tasks[0].baseline[0];expect(tally([{...row,passed:true,evidence_backed:false}])).toMatchObject({passed:1,supported:0});
});

it('refuses raw traces and private payloads even inside storyboard additions',()=>{
 for (const key of ['raw_trace','messages','dom','model_output','truth','expected','api_key']) {
  expect(parseInvestigation(JSON.stringify({...recording, storyboard:{[key]:'hidden'}})).ok).toBe(false);
 }
});

it('keeps full protocol and verdicts accessible on demand without changing recorded data', async()=>{
 sessionStorage.clear(); const before=JSON.stringify(recording);const host=document.createElement('div');document.body.append(host);const root=createRoot(host);
 await act(async()=>{root.render(<InvestigationPage/>);await new Promise(r=>setTimeout(r,100));});
 await act(async()=>{await new Promise(r=>setTimeout(r,100));});
 const details=host.querySelector<HTMLDetailsElement>('.experiment-details')!;
 expect(details.open).toBe(false);expect(details.textContent).toContain('inconclusive');expect(details.textContent).toContain('Not supported');
 expect(details.textContent).toContain('No verified findings');expect(details.textContent).toContain('Historical baseline');
 const open=[...host.querySelectorAll('button')].find(b=>b.textContent==='View verdicts and experiment details')!;
 const scroll=Element.prototype.scrollIntoView;Element.prototype.scrollIntoView=()=>{};
 await act(async()=>{open.click();});expect(details.open).toBe(true);
 expect(document.activeElement).toBe(details.querySelector('summary'));Element.prototype.scrollIntoView=scroll;
 expect(JSON.stringify(recording)).toBe(before);act(()=>root.unmount());host.remove();
});
