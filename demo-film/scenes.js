(() => {
/* Static reusable scenes: facts and event text come exclusively from the adapter. */
const {presentation:p, scenes:configuredScenes, evidence:e} = window.FILM;
const esc = value => String(value ?? 'Unavailable').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const lines = value => value.map(esc).join('<br>');
const headline = s => `<h1>${lines(s.headline)}</h1>`;
const count = value => value == null ? '—' : Number(value).toLocaleString('en-US');
const proof = text => `<div class="proof">${esc(text)}</div>`;
const symbol = `<svg viewBox="0 0 48 48" fill="none" aria-hidden="true"><path d="M10 34V16h13M23 34h15V16M10 34l28-18" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/><circle cx="10" cy="34" r="4" fill="currentColor"/><circle cx="38" cy="16" r="4" fill="currentColor"/></svg>`;
const brand = `<div class="brand"><span class="mark">${symbol}</span>${esc(p.brand)}</div>`;
const equipment = `<svg class="equipment" viewBox="0 0 240 120" fill="none" aria-hidden="true"><path d="M42 87h154l-16-54H88L63 61H42v26Z" fill="currentColor" fill-opacity=".09" stroke="currentColor" stroke-width="2"/><path d="M100 32V17h61v16M88 52h67M90 65h53M178 54l9 29" stroke="currentColor" stroke-width="2"/><circle cx="72" cy="91" r="15" fill="var(--surface)" stroke="currentColor" stroke-width="2"/><circle cx="176" cy="91" r="15" fill="var(--surface)" stroke="currentColor" stroke-width="2"/></svg>`;
const workflow = () => `<div class="workflow">${p.workflow.map((stage,i)=>`<article><span class="step-index">${String(i+1).padStart(2,'0')}</span><h2>${esc(stage)}</h2>${i<p.workflow.length-1?'<span class="step-arrow">↗</span>':''}</article>`).join('')}</div>`;
const browser = (closing=false) => `<div class="browser ${closing?'closing-browser':''}"><div class="browser-chrome"><span class="traffic">● ● ●</span><span class="address">${esc(p.illustration.browser_label)}</span><span>↗</span></div><div class="browser-content"><div class="browser-title">${esc(p.illustration.catalog_title)}<span class="micro">ILLUSTRATIVE LAYOUT</span></div><div class="browser-grid">${[0,1].map(()=>`<div class="browser-item">${equipment}<strong>${esc(p.illustration.item_label)}</strong><div class="ghost-line"></div><span class="detail-link">${esc(p.illustration.detail_label)} ↗</span></div>`).join('')}</div><div class="terms-location">${closing?'↗':'⌕'} ${esc(closing?p.illustration.closing_label:p.illustration.challenge)}</div></div></div>`;
const journey = () => {
  const focus=e.featured.focus;
  const index=e.featured.events.findIndex(step=>step.ref===focus?.ref);
  // Neighbor selection stays in archive order. The manifest controls the full sequence and focus.
  const neighbors=e.featured.events.slice(Math.max(0,index-1),Math.max(0,index-1)+3);
  return `<div class="journey archive"><div class="task"><span class="micro">RECORDED TASK · ${esc(e.featured.arm)}</span><h2>${esc(e.featured.question)}</h2></div><div class="action-focus ${focus?.category==='browser tool'?'tool-event':''}" ${focus?`data-ref="${esc(focus.ref)}"`:''}><span class="micro">${esc(focus?.category??'Recorded evidence')} ${focus?`/ EVENT ${esc(focus.event)}`:''}</span><div class="action-icon">${focus?.category==='browser tool'?'↧':'↗'}</div><h3>${esc(focus?.text??e.featured.availability)}</h3><span class="action-note">${focus?'Exact archived event · Composed view':'No substitute events shown'}</span></div><div class="event-progression">${neighbors.map(step=>`<article class="${step.ref===focus?.ref?'selected':''}" data-ref="${esc(step.ref)}" title="${esc(step.text)}"><span>${esc(step.category)} · ${esc(step.event)}</span><strong>${esc(step.text)}</strong></article>`).join('')}</div><div class="timeline-label"><span>ARCHIVED SEQUENCE</span><span>${count(e.featured.event_count)} selected entries</span></div><div class="timeline">${e.featured.events.map((step,i)=>`<span class="timeline-event ${step.ref===focus?.ref?'active':''}" title="${esc(step.text)}" data-ref="${esc(step.ref)}"><i></i><small>${esc(step.event)}</small></span>`).join('')}</div></div>`;
};
const listing = after => `<article class="listing ${after?'after':'before'}"><div class="listing-header"><span class="micro">${esc(after?p.illustration.after_label:p.illustration.before_label)}</span><span class="layout-tag">ILLUSTRATIVE</span></div><div class="listing-product">${equipment}<div><h2>${esc(p.illustration.item_label)}</h2><div class="ghost-line"></div></div></div>${after?`<div class="surfaced-terms">${p.illustration.field_labels.map(label=>`<div><span>↗</span>${esc(label)}<small>Existing field</small></div>`).join('')}</div>`:`<div class="listing-empty"><span class="ghost-line"></span><span class="ghost-line short"></span></div><div class="buried-terms"><span>${esc(p.illustration.detail_label)} ↗</span><small>${p.illustration.field_labels.map(esc).join(' · ')}</small></div>`}</article>`;
const meter = (arm,type) => {
  if(type==='passes') return `<div class="pass-strip" aria-label="${esc(arm)} task outcomes">${e.rows.map(row=>`<i class="${row[arm].supported===true?'passed':row[arm].supported===false?'failed':'unknown'}" title="${esc(row.id)}: ${row[arm].supported===true?'Evidence-supported pass':row[arm].supported===false?'Not passed':'Unavailable'}"></i>`).join('')}</div>`;
  const value=e[arm].requests, max=Math.max(e.original.requests??0,e.modified.requests??0);
  return `<div class="request-meter"><i style="width:${value==null||max===0?0:100*value/max}%"></i></div>`;
};
const components={
  hook:s=>`<div class="copy"><p class="eyebrow">${esc(s.eyebrow)}</p>${headline(s)}<p>${lines(s.body)}</p></div>${browser()}<div class="agent-command"><span class="agent-icon">${symbol}</span><div><span class="micro">ILLUSTRATIVE AGENT GOAL</span><strong>${p.illustration.goal.map(esc).join(' ')}</strong></div><span class="command-arrow">↗</span></div>${proof(s.provenance)}`,
  product:s=>`${headline(s)}<div class="identity">${symbol}</div><p class="subline">${lines(s.body)}</p>${workflow()}${proof(s.provenance)}`,
  behavior:s=>`${headline(s)}<span class="recorded-badge">● RECORDED EVIDENCE</span>${journey()}${proof(e.featured.focus?.category==='browser tool'?'Browser-tool behavior · Not a verified website defect':s.provenance)}`,
  improvement:s=>`${headline(s)}<div class="intervention-label">${e.proposal.owner_selected===true?'OWNER-SELECTED INTERVENTION':'RECORDED PROPOSAL'}${e.proposal.validation==='unvalidated'?' · NOT INDEPENDENTLY VERIFIED':''}</div><div class="listing-pair">${listing(false)}<div class="change-arrow">→</div>${listing(true)}</div>${proof(s.provenance+' · No invented rental values')}`,
  results:s=>`${headline(s)}<span class="recorded-badge">● RECORDED COMPARISON</span><div class="metrics">${[['passes','Evidence-supported passes','supported'],['requests','Model requests','requests']].map(([type,label,field])=>`<article class="metric-panel"><span class="metric-label">${label}</span><div class="metric-value" data-metric="${type}">${count(e.original[field])}${type==='passes'?'/'+count(e.task_count):''}<span>→</span><em>${count(e.modified[field])}${type==='passes'?'/'+count(e.task_count):''}</em></div><div class="comparison-lines"><div><span>Original</span>${meter('original',type)}</div><div><span>Modified</span>${meter('modified',type)}</div></div><p class="metric-note">${type==='passes'?`${count(e.task_count)} tasks · Evidence-supported outcomes`:esc(e.request_change_label)}</p></article>`).join('')}</div><div class="verdicts">Frozen: ${esc(e.verdicts.frozen)}<span>Exploratory: ${esc(e.verdicts.exploratory)}</span></div>${proof(e.qualification)}`,
  vision:s=>`${headline(s)}<p class="closing-line">${esc(s.body?.[0]??'A feedback loop for the agentic web.')}</p>${browser(true)}${workflow()}${p.repository_verified?`<a class="repo" href="${esc(p.repository)}">${esc(p.repository.replace(/^https:\/\//,''))} ↗</a>`:''}${proof(s.provenance)}`
};
const scene=configuredScenes.find(s=>s.id===document.body.dataset.scene);
if(!scene) throw new Error('Scene is not enabled in the manifest');
const ordinal=configuredScenes.indexOf(scene)+1;
const visualNumber=['hook','product','behavior','improvement','results','vision'].indexOf(scene.component)+1;
document.querySelector('main').innerHTML=`<section class="stage s${visualNumber} emphasis-${esc(scene.emphasis)}">${brand}<div class="scene-no">${String(ordinal).padStart(2,'0')} / ${String(configuredScenes.length).padStart(2,'0')}</div>${components[scene.component](scene)}</section>`;
for(const node of document.querySelectorAll('.action-focus h3')){
 let size=43;
 while(node.scrollHeight>160&&size>24) node.style.fontSize=`${--size}px`;
}
for(const node of document.querySelectorAll('.metric-value')){
 let size=104;
 while(node.scrollWidth>node.clientWidth&&size>36) node.style.fontSize=`${--size}px`;
}
})();
