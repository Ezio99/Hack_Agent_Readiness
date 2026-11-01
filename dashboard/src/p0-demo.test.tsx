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
 expect(host.textContent).toContain('2/4 → 3/4 evidence-supported passes');
 expect(host.textContent).toContain('50 → 29');
 expect(host.textContent).toContain('Improvement is not established');
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
