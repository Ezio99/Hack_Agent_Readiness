/** PRESENTATION-ONLY styling for the captured storefront pages, applied at display time inside the dashboard's sandboxed frames.
 *  It is CSS only: it adds one <style> element and never changes text, links, structure or attributes of the captured HTML, and the captured snapshots, exports and experiment inputs are untouched.
 *  The experiments (baseline, unmodified repeat, patched) ran on the ORIGINAL pages, not on this appearance. */
export const THEME_MARK = 'data-presentation-theme="true"';

export const THEME_CSS = `
:root{--ink:#14232b;--muted:#5b6b73;--line:#dfe6e3;--brand:#0f6b5c;--brand-d:#0a4a40;--accent:#e8a21a;--bg:#f4f7f5}
html{background:var(--bg)}
body{margin:0!important;font:16px/1.55 ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif!important;color:var(--ink);background:var(--bg)!important;-webkit-font-smoothing:antialiased}
header{max-width:none!important;padding:0!important;margin:0!important;background:linear-gradient(120deg,var(--brand-d),var(--brand));box-shadow:0 2px 12px rgba(10,74,64,.25)}
header nav{max-width:1000px;margin:0 auto;padding:0 20px;display:flex;align-items:center;gap:4px;min-height:60px;flex-wrap:wrap}
header nav::before{content:"";width:30px;height:30px;margin-right:14px;border-radius:9px;background:conic-gradient(from 210deg,var(--accent),#fff3cf,var(--accent));box-shadow:inset 0 0 0 5px var(--brand-d),0 0 0 2px rgba(255,255,255,.35)}
header nav a{margin:0!important;padding:8px 14px;border-radius:999px;color:#e8f5f1!important;text-decoration:none!important;font-weight:600;font-size:.95rem}
header nav a:hover{background:rgba(255,255,255,.16)}
header nav a:first-of-type{margin-left:0}
main{max-width:1000px!important;margin:0 auto!important;padding:32px 20px 48px!important}
main>h1{font-size:2.1rem;line-height:1.15;letter-spacing:-.02em;font-weight:800;margin:0 0 6px}
main>h1+p{font-size:1.1rem;color:var(--muted);margin:0 0 20px}
main:has(>p>a[href="/tools"]){margin-top:28px!important;padding:56px 40px!important;border-radius:22px;background:radial-gradient(900px 300px at 85% -10%,rgba(232,162,26,.28),transparent),linear-gradient(135deg,#e5f3ee,#fbfdfc);border:1px solid var(--line);max-width:960px!important}
main:has(>p>a[href="/tools"])>h1{font-size:3rem}
main>p>a[href="/tools"]{display:inline-block;margin-top:8px;padding:13px 26px;border-radius:12px;background:var(--brand);color:#fff!important;font-weight:700;text-decoration:none!important;box-shadow:0 6px 16px rgba(15,107,92,.3)}
main>ul{display:grid!important;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:18px;padding:0!important;margin:20px 0!important}
li.card{list-style:none;margin:0!important;padding:0 0 18px!important;border:1px solid var(--line)!important;border-radius:16px;background:#fff;overflow:hidden;box-shadow:0 1px 2px rgba(20,35,43,.06),0 8px 22px rgba(20,35,43,.06);display:flex;flex-direction:column;transition:transform .15s,box-shadow .15s}
li.card:hover{transform:translateY(-3px);box-shadow:0 2px 4px rgba(20,35,43,.08),0 14px 30px rgba(20,35,43,.12)}
li.card::before{content:"";display:block;height:92px;background:linear-gradient(135deg,#cfe9e1,#f6e7c1);border-bottom:1px solid var(--line)}
li.card:nth-child(3n+2)::before{background:linear-gradient(135deg,#f6e7c1,#d7e6f3)}
li.card:nth-child(3n)::before{background:linear-gradient(135deg,#d7e6f3,#cfe9e1)}
li.card a{color:var(--ink)!important;text-decoration:none!important}
li.card h3{margin:16px 18px 4px;font-size:1.12rem;font-weight:700;letter-spacing:-.01em}
li.card a:hover h3{color:var(--brand)}
li.card p{margin:0 18px;color:var(--muted);font-size:.93rem}
li.card p:nth-of-type(2){margin-top:12px;align-self:flex-start;padding:4px 12px;border-radius:999px;background:#fff4d6;color:#7a4b00;font-weight:700;font-size:.9rem;border:1px solid #f0d58a}
table{width:100%;max-width:640px;border-collapse:separate!important;border-spacing:0;background:#fff;border:1px solid var(--line);border-radius:14px;overflow:hidden;box-shadow:0 1px 2px rgba(20,35,43,.06)}
th,td{border:0!important;border-bottom:1px solid var(--line)!important;padding:13px 18px!important;text-align:left}
tr:last-child th,tr:last-child td{border-bottom:0!important}
th{width:38%;background:#f1f6f4;color:var(--muted);font-weight:600;font-size:.9rem}
td{font-weight:700}
main a{color:var(--brand)}
dl{max-width:640px}
footer{max-width:none!important;margin:0!important;padding:22px 20px!important;background:#10262c;color:#a9bcc3;text-align:center;font-size:.9rem}
`;

export function themeStyleTag(): string {
  return `<style ${THEME_MARK}>${THEME_CSS}</style>`;
}
