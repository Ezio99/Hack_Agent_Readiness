// Pre-deployment safety check for the static build (dashboard/dist). No dependencies. Exit 1 on any finding.
//   node scripts/check-dist.mjs            -> a public build WITHOUT replay data must contain no replays/ directory
//   ALLOW_REPLAYS=1 node scripts/check-dist.mjs -> replays/ is permitted (only after the exact files were approved for publication)
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";

const root = process.env.DIST_DIR ?? new URL("../dist", import.meta.url).pathname;   // DIST_DIR is for tests only
const allowReplays = process.env.ALLOW_REPLAYS === "1";
const files = [];
const walk = (d) => readdirSync(d).forEach((n) => { const p = join(d, n); statSync(p).isDirectory() ? walk(p) : files.push(p); });
try { walk(root); } catch { console.error("dist/ not found: run `npm run build` first"); process.exit(1); }

const findings = [];
const BAD_NAMES = [/(^|\/)\.env/, /(^|\/)runs\//, /\.zip$/, /\.rar$/, /(^|\/)screenshots\//, /trace\.jsonl$/, /model-response-/, /history\.json$/, /\.map$/];
const BAD_CONTENT = [
  [/META_MODEL_API_KEY/, "credential variable name"], [/\bsk-[A-Za-z0-9]{16,}/, "key-like token"], [/Bearer\s+[A-Za-z0-9._-]{16,}/, "bearer token"],
  [/api\.meta\.ai|dev\.meta\.ai\/api/, "model API endpoint"], [/\/home\/[a-z]|\/Users\/[A-Za-z]|\/tmp\/claude/, "local path"], [/127\.0\.0\.1:\d+/, "localhost port"],
];
for (const f of files) {
  const rel = relative(root, f);
  if (rel.startsWith("replays/") && !allowReplays) findings.push(`${rel}: replay data present in a build that is not approved to include it`);
  if (BAD_NAMES.some((re) => re.test(rel)) && !(rel.startsWith("replays/") && allowReplays && /\.json$/.test(rel))) findings.push(`${rel}: forbidden file type or location`);
  if (/\.(js|css|html|json|svg|txt|md)$/.test(rel)) {
    const text = readFileSync(f, "utf8");
    for (const [re, label] of BAD_CONTENT) if (re.test(text)) findings.push(`${rel}: ${label}`);
  }
}
const total = files.reduce((a, f) => a + statSync(f).size, 0);
console.log(`dist: ${files.length} files, ${total} bytes; replays included: ${files.some((f) => relative(root, f).startsWith("replays/"))}`);
for (const f of files) console.log(`  ${relative(root, f)} (${statSync(f).size})`);
console.log(findings.length ? `CHECK FAILED:\n - ${findings.join("\n - ")}` : "CHECK PASSED: no credentials, local paths, traces or unapproved replay data in dist/");
process.exit(findings.length ? 1 : 0);
