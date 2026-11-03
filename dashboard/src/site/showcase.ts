/** The featured demo: ONE source of truth for the website, evaluations and story that Home, the Larkspur journey (#/lifecycle), the workspace and
 *  the featured reports share. Home and the journey's static parts call no API, so the recorded numbers come from `showcase/larkspur.json`,
 *  exported from the product's own report of the paid live evaluation (scripts/showcase/export_larkspur_showcase.py). Nothing here is simulated. */
import data from './showcase/larkspur.json';

const frameUrls = import.meta.glob('./showcase/frames/*.webp', { eager: true, query: '?url', import: 'default' }) as Record<string, string>;
export const showcaseFrame = (name: string | null | undefined): string | undefined => name ? frameUrls[`./showcase/frames/${name}.webp`] : undefined;

export interface LiveTrial { task: number; variant: string; passed: boolean; correct: boolean; requests: number; limit: number; seconds: number; cost_usd: number; dead_end: boolean; path?: string[] }
export interface LiveStep { step: number; path: string | null; memory: string | null; goal: string | null; frame: string | null }
export interface LiveRecord {
  id: string; title: string; started_at: string; finished_at: string; cost_usd: number;
  agent: { model: string; reasoning_effort: string; max_completion_tokens: number; profile: string };
  tasks: { n: number; task_id: string; wording: string; capability: string | null }[];
  totals: Record<string, { requests: number; seconds: number; cost_usd: number }>;
  passed: Record<string, number>; correct: Record<string, number>;
  trials: LiveTrial[];
  journeys: Record<string, { answer: string | string[]; steps: LiveStep[] }>;
}

/** The featured result: the live evaluation of Original vs IMPROVED (the three judge tasks, six agents), as the product's report states it. */
export const LIVE = data.live as unknown as LiveRecord;
/** The first live evaluation (Original vs Modified, six tasks, 12 agents): the run the recommendations came from. Kept as history. */
export const FIRST_LIVE = data.first_live as unknown as LiveRecord;

/** The featured experiment (2026-11-04): "Before" = the original college site visually redesigned (snapshot polishedoriginal), evaluated alone;
 *  "After" = the same design with that evaluation's recommendations applied (snapshot modifiedpolished), evaluated alone. Same frozen tasks and agent. */
export const BEFORE = data.before as unknown as LiveRecord;
export const AFTER = data.after as unknown as LiveRecord;
export const BEFORE_V = 'polishedoriginal', AFTER_V = 'modifiedpolished';
/** The three changes the Before evaluation recommended, as applied to the After website (sites/larkspur/modified_polished.py). */
export const AFTER_CHANGES: { id: string; title: string; change: string }[] = [
  { id: 'facts', title: 'Every fact on every course card', change: 'Fee, duration, level, class day, campus, seats left and materials on each card, so a comparison needs no course page.' },
  { id: 'dead-end', title: 'No dead end', change: 'An agent guessed /courses/introduction-to-python from the course name and got “not found”. Course addresses that follow the name now lead to the course.' },
  { id: 'structured', title: 'Structured course data', change: 'Each course page describes the course in schema.org data with the same values the page shows, and the catalogue lists every course.' },
];
/** Superseded earlier redesign trials A and B (built on the already-improved site; kept as history, never featured). */
export const TRIAL_A = data.polished_v1 as unknown as LiveRecord;
export const TRIAL_B = data.polished_v2 as unknown as LiveRecord;

/** The product's own page audit (the readiness report's structural rules) of each version: what is still wrong with the pages themselves. */
export const PAGE_AUDIT = data.page_audit as Record<'original' | 'modified' | 'improved', string[]>;

export const FEATURED = {
  site: 'larkspur',
  name: 'Larkspur Community College',
  short: 'Larkspur',
  kind: 'short-course catalogue',
  host: 'larkspur-college',
  /** the featured live evaluation (Original vs Improved) and its report */
  liveEvaluation: LIVE.id,
  liveDate: '3 Nov 2026',
  /** the first live evaluation (Original vs Modified), where the recommendations came from */
  firstLiveEvaluation: FIRST_LIVE.id,
  /** the earlier pre-recorded research run of the same suite */
  researchRun: 'm7-larkspur-browser-1',
  /** the frozen tasks judges run live: fee and seats; weekend class day and level (needs the Improved cards); fee and duration */
  judgeSuite: 'larkspur-core@v3',
  judgeTasks: ['gen-23f1802ee0-n', 'gen-8334922e62-n', 'gen-f302fa8fe2-n'],
} as const;

export const VERSIONS = {
  original: { label: 'Original', blurb: 'The website as it was: each course card shows only a name, a subject and a one-line summary. Every other fact is one click deeper.' },
  modified: { label: 'Modified', blurb: 'The first fix: course cards also show fee, duration, level and seats left.' },
  improved: { label: 'Improved', blurb: 'Every recommendation applied: all seven facts on every card, browse pages, a working filter, a comparison table, structured data and no dead ends.' },
} as const;

/** Which deciding facts each version states on its course cards (from the rendered pages; tested against the site source). */
export const CARD_FACTS: { fact: string; original: boolean; modified: boolean; improved: boolean }[] = [
  { fact: 'Course fee', original: false, modified: true, improved: true },
  { fact: 'Duration', original: false, modified: true, improved: true },
  { fact: 'Level', original: false, modified: true, improved: true },
  { fact: 'Seats left', original: false, modified: true, improved: true },
  { fact: 'Class day', original: false, modified: false, improved: true },
  { fact: 'Campus', original: false, modified: false, improved: true },
  { fact: 'Materials', original: false, modified: false, improved: true },
];

export interface Improvement { id: string; title: string; problem: string; recommendation: string; change: string; tryPath: string; preview?: string }

/** Each change on the Improved site, the problem agents hit, and the recommendation it answers. Problems cite the live evaluation's recorded traces. */
export const IMPROVEMENTS: Improvement[] = [
  { id: 'facts', title: 'Every deciding fact on every card',
    problem: 'On the Original site agents opened course pages one at a time. Fee-and-seats questions ran out of requests after 3 of 14 courses. Once fee and seats were on the cards (Modified), the same question took 3 requests. Class-day and campus questions still took 11–13 requests, because those facts were still one click deeper.',
    recommendation: 'State fee, duration, level, seats left, class day, campus and materials on each card of /courses.',
    change: 'All seven facts on every course card.', tryPath: '/courses', preview: 'site-improved-courses' },
  { id: 'filter', title: 'A catalogue filter that works',
    problem: 'Agents look for filters. One opened the catalogue to “find filters”, then typed /courses?level=Intermediate&campus=Northside by hand and got a 404.',
    recommendation: 'Let customers and agents narrow the catalogue by the attributes they ask about.',
    change: 'A plain filter form on /courses (level, campus, class day, including “Weekend”). Every result is a real page, and hand-typed filter URLs in any order or case open the right result.',
    tryPath: '/courses?level=Intermediate&campus=Northside', preview: 'site-improved-courses-filter' },
  { id: 'browse', title: 'Browse pages for campus, day, level and subject',
    problem: 'Questions like “Intermediate courses at Northside” or “Beginner courses at the weekend” had no page that answered them.',
    recommendation: 'Link one page per campus, class day, level and subject from the catalogue.',
    change: 'Linked pages such as /courses/campus/northside and /courses/day/weekend.', tryPath: '/courses/day/weekend' },
  { id: 'compare', title: 'One comparison table',
    problem: 'Original agents used 12–13 of 14 requests on five of six tasks, revisiting the catalogue between course pages.',
    recommendation: 'Put the facts a comparison needs on one page.',
    change: 'Every course and all seven facts in one table, cheapest first. In the live re-evaluation every Improved agent answered from this table, in 2 requests.', tryPath: '/courses/compare', preview: 'site-improved-courses-compare' },
  { id: 'dead-ends', title: 'No dead ends',
    problem: 'Agents guessed course URLs from course names and hit 404s: /courses/introduction-to-python (the page is /courses/intro-to-python), /courses/yoga-for-beginners, and /courses/ with a trailing slash.',
    recommendation: 'Fix or remove the failing link or control; make course URLs predictable.',
    change: 'Course URLs that follow the course name, the URLs agents tried, trailing slashes and /course/… all redirect to the right page.',
    tryPath: '/courses/introduction-to-python', preview: 'site-improved-courses-intro-to-python' },
  { id: 'structured', title: 'Structured course data',
    problem: 'No course page described itself in a machine-readable way.',
    recommendation: 'Describe each course with schema.org JSON-LD using the same values the page shows.',
    change: 'Course, Offer and CourseInstance data (fee, seats, level, day, campus, weeks) on every course page, and a list of all courses on /courses.',
    tryPath: '/courses/intro-to-python' },
];

/** The product journey, in order. Each step is a section of #/lifecycle. */
export const JOURNEY = [
  { id: 'website', n: '01', label: 'Website', blurb: 'The business and its customers' },
  { id: 'tasks', n: '02', label: 'Generate tasks', blurb: 'Customer questions, checked against the site' },
  { id: 'review', n: '03', label: 'Review', blurb: 'The owner approves a frozen task set' },
  { id: 'evaluate', n: '04', label: 'Evaluate', blurb: 'Real browser agents, live' },
  { id: 'recommendations', n: '05', label: 'Recommendations', blurb: 'What slowed agents down, and what to change' },
  { id: 'improve', n: '06', label: 'Improve', blurb: 'The website, changed' },
  { id: 'reevaluate', n: '07', label: 'Re-evaluate', blurb: 'The same tasks on the new site' },
  { id: 'compare', n: '08', label: 'Compare', blurb: 'Before and after, live' },
] as const;

export const trialOf = (variant: string, task: number, run: LiveRecord = LIVE) => run.trials.find(t => t.variant === variant && t.task === task);
export const journeyOf = (variant: string, task: number, run: LiveRecord = LIVE) => run.journeys[`${variant}-${task}`];
/** The featured task: the class-day question that failed on Original and on the first fix, and that only the Improved site answers on its cards. */
export const FEATURED_TASK = 2;
export const fewerPct = (a: number, b: number) => Math.round(100 * (a - b) / a);
