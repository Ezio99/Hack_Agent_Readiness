/** One-shot, in-memory handoff of a sanitized export from the evaluation workspace to the Replay archive. */
let pending: { data: unknown; label: string } | null = null;
export const handOff = (data: unknown, label: string) => { pending = { data, label }; };
export const takeHandoff = () => { const p = pending; pending = null; return p; };
