/** I2 (M9): the RETROSPECTIVE evidence audit of the two paid larkspur-core v2 runs (collaboration/reports/m9-grading-audit.md, 2026-11-03).
 *  Counts only, per evaluation, as audited from the recorded evidence. NOT an official score: official grader v1 stays the grade of record and
 *  grader v2 stays a labelled post-hoc rescore. Shown only for the two audited evaluations. */
export interface AuditView { correct: { original: number; modified: number }; verified: { original: number; modified: number }; v1FalseNegatives: { original: number; modified: number }; of: number }

export const AUDIT_DATE = '3 Nov 2026';
export const GRADING_AUDIT: Record<string, AuditView> = {
  'm7-larkspur-browser-1': { correct: { original: 3, modified: 5 }, verified: { original: 1, modified: 4 }, v1FalseNegatives: { original: 1, modified: 4 }, of: 6 },
  'eval-e529db2aafecbfddd21e5c571eb85243': { correct: { original: 2, modified: 5 }, verified: { original: 1, modified: 5 }, v1FalseNegatives: { original: 1, modified: 3 }, of: 6 },
};
