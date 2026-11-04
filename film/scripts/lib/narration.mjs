// Load the narration cue sheet (src/narration.ts, the single source of truth) from Node scripts, via the esbuild that ships with Remotion.
import { build } from 'esbuild';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

export const FILM = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
export async function loadNarration() {
  const r = await build({ entryPoints: [join(FILM, 'src', 'narration.ts')], bundle: true, format: 'esm', platform: 'node', write: false, logLevel: 'silent' });
  return import('data:text/javascript;base64,' + Buffer.from(r.outputFiles[0].text).toString('base64'));
}

/** The audition clips and the lines each one reads (vo/AUDITION.md; the pictures they are laid under: src/Voice.tsx EXCERPTS). */
export const AUDITION = [
  ['a1.college', 'a1.designed', 'a1.question'],
  ['a2.low', { id: 'a2.stops', text: 'So it stops itself, before finding all four matching courses.' }],
  ['a5.brand', 'a5.tagline'],
];
