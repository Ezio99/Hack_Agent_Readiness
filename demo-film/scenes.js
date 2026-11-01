(() => {
/* Reusable static compositions. All run-specific facts come from film-data.js. */
const {presentation: p, scenes: configuredScenes, evidence: e, captures} = window.FILM;
const esc = value => String(value ?? 'Unavailable').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const lines = value => value.map(esc).join('<br>');
const headline = scene => `<h1>${lines(scene.headline)}</h1>`;
const brand = `<div class="brand"><span class="mark">&lt;›</span> ${esc(p.brand)}</div>`;
const workflow = (numbers=true) => `<div class="workflow">${p.workflow.map((s,i)=>`<article>${numbers?`<small>${String(i+1).padStart(2,'0')}</small>`:''}<h2>${esc(s)}</h2></article>`).join('')}</div>`;
const image = (path, alt) => `<div class="capture"><img src="../${esc(path)}" alt="${esc(alt)}"></div>`;
const proof = text => `<div class="proof">${esc(text)}</div>`;
const count = value => value == null ? '—' : Number(value).toLocaleString('en-US');
const outcome = value => value === true ? 'Pass' : value === false ? 'Fail' : 'Unavailable';
const event = step => step ? `<div class="focus-card surface"><span class="event-meta">${esc(step.category)} · Event ${esc(step.event)}</span><strong>${esc(step.text)}</strong></div>` : '<div class="focus-card surface">No public event selected</div>';
const sequence = () => `<div class="archive surface"><h2>${esc(e.featured.question)}</h2><p>${esc(e.featured.task_id)} · ${esc(e.featured.arm)} · Recorded evidence</p>${e.featured.events.length ? `<ol>${e.featured.events.slice(0,8).map(s=>`<li><span>${esc(s.category)} · ${esc(s.event)}</span>${esc(s.text)}</li>`).join('')}</ol>${e.featured.events.length>8?`<p>+ ${count(e.featured.events.length-8)} additional selected event(s)</p>`:''}` : `<p>${esc(e.featured.availability)}</p>`}</div>`;
const taskRows = () => `<div class="outcome-table surface"><table><caption>Recorded contemporary outcomes · Evidence-supported passes</caption><thead><tr><th>Task</th><th>Original</th><th>Modified</th></tr></thead><tbody>${e.rows.slice(0,5).map(r=>`<tr><td>${esc(r.id)}</td><td>${outcome(r.original.supported)}</td><td>${outcome(r.modified.supported)}</td></tr>`).join('')}</tbody></table>${e.rows.length>5?`<p>Showing 5 of ${count(e.task_count)} tasks; aggregates include all selected tasks.</p>`:''}</div>`;
const components = {
  hook: s => `<div class="copy"><p class="eyebrow">${esc(s.eyebrow)}</p>${headline(s)}<p>${lines(s.body)}</p></div><div class="concept surface"><div class="prompt"><span>ILLUSTRATIVE USER GOAL</span>${lines(p.illustration.goal)}</div><div class="concept-grid">${p.illustration.actions.map((x,i)=>`${i?'<span class="arrow">›</span>':''}<div class="concept-card"><b>${esc(x)}</b><div class="skeleton"></div><div class="skeleton" style="width:65%"></div><div class="terms">Hire terms</div></div>`).join('')}</div><div class="trace-line"><i></i><span></span><i></i><span></span><i></i><span></span><i></i></div></div>${proof(s.provenance)}`,
  product: s => `${headline(s)}<div class="large-mark">&lt;›</div><p class="subline">${lines(s.body)}</p>${workflow()}${proof(s.provenance)}`,
  behavior: s => `<div class="copy"><p class="eyebrow">Recorded evaluation</p>${headline(s)}<p>${esc(e.featured.task_id)}<br><span class="cyan">${count(e.featured.event_count)} archived events.</span></p></div><div class="recording"><span class="pill">${captures.storyboard?'Actual recorded report · UI capture':'Archived evidence · Composed view'}</span>${captures.storyboard?image(captures.storyboard,'Unmodified recorded dashboard storyboard for selected task'):sequence()}</div><div class="event"><span class="caption">${s.emphasis==='sequence'?'ARCHIVED EVENT':'FEATURED EVENT'} · ${esc(e.featured.focus?.category ?? 'Unavailable')}</span>${event(e.featured.focus)}</div>${proof(e.featured.focus?.category==='browser tool'?'Recorded tool interaction · Not a verified website defect':s.provenance)}`,
  improvement: s => `<div class="copy"><p class="eyebrow">${esc(s.eyebrow)}</p>${headline(s)}</div><div class="owner"><span class="caption">${e.proposal.owner_selected===true?'OWNER-SELECTED INTERVENTION':'RECORDED PROPOSAL'}</span>${captures.suggestion?image(captures.suggestion,'Actual recorded proposal card'): `<div class="proposal-card surface"><strong>${esc(e.proposal.label)}</strong><p>Validation: ${esc(e.proposal.validation)}</p><p>Basis: ${esc(e.proposal.basis)}</p></div>`}</div><div class="listing-concept surface"><span class="pill">Illustrative layout</span><h2>${lines(s.body)}</h2>${p.illustration.field_labels.map((label,i)=>`<div class="term"><span>${String(i+1).padStart(2,'0')}</span>${esc(label)}</div>`).join('')}<div class="caption" style="margin-top:18px">Existing fields → Listing card<br>Concept only · No rental values shown</div></div>${proof(`${e.proposal.owner_selected===true?'Owner-selected · ':''}${e.proposal.validation==='unvalidated'?'Not independently verified · ':''}${s.provenance}`)}`,
  results: s => `${headline(s)}<div class="metrics"><div><div class="metric-label">Evidence-supported passes · Original → Modified</div><div class="metric-value" data-metric="passes">${count(e.original.supported)}/${count(e.task_count)}<span>→</span><em>${count(e.modified.supported)}/${count(e.task_count)}</em></div></div><div><div class="metric-label">Model requests · Original → Modified</div><div class="metric-value" data-metric="requests">${count(e.original.requests)}<span>→</span><em>${count(e.modified.requests)}</em></div><div class="metric-note">${esc(e.request_change_label)}</div></div></div><div class="rows">${captures.outcomes?image(captures.outcomes,'Actual recorded contemporary task outcomes'):taskRows()}<div class="caption">RECORDED OUTCOMES<br>${count(e.task_count)} tasks<br><br>Frozen: ${esc(e.verdicts.frozen)}<br>Exploratory: ${esc(e.verdicts.exploratory)}</div></div>${proof(e.qualification)}`,
  vision: s => `${headline(s)}<div class="end-mark"><span class="mark">&lt;›</span></div>${workflow(false)}${p.repository_verified?`<a class="repo" href="${esc(p.repository)}">${esc(p.repository.replace(/^https:\/\//,''))} ↗</a>`:''}${proof(s.provenance)}`
};
const key = document.body.dataset.scene;
const scene = configuredScenes.find(s => s.id === key);
if (!scene) throw new Error('Scene is not enabled in the manifest');
const ordinal = configuredScenes.indexOf(scene) + 1;
const visualNumber = ['hook','product','behavior','improvement','results','vision'].indexOf(scene.component)+1;
document.querySelector('main').innerHTML = `<section class="stage s${visualNumber} emphasis-${esc(scene.emphasis)}">${brand}<div class="scene-no">${String(ordinal).padStart(2,'0')} / ${String(configuredScenes.length).padStart(2,'0')}</div>${components[scene.component](scene)}</section>`;
// Keep longer counts legible inside the fixed metric column.
for (const node of document.querySelectorAll('.metric-value')) {
  let size = 110;
  while (node.scrollWidth > node.clientWidth && size > 45) node.style.fontSize = `${--size}px`;
}

})();
