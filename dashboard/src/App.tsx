import { lazy, Suspense, useEffect } from 'react';
import { useRoute } from './site/router';
import { Home } from './site/Home';
import { Workspace } from './site/workspace/Workspace';
import { Lifecycle } from './site/lifecycle/Lifecycle';
import { ReportPage } from './site/lifecycle/Report';

/** `#/demo` is the featured Larkspur journey (the same page as `#/lifecycle`). The earlier Ironbark scroll story carries its own evidence frames and
 *  lives in the archive at `#/demo/ironbark` (its scene deep links still work); the archive also carries the pre-redesign app. Both load on demand. */
const Demo = lazy(() => import('./site/demo/Demo').then(m => ({ default: m.Demo })));
const Classic = lazy(() => import('./legacy/Classic'));
const Story = lazy(() => import('./site/story/Story').then(m => ({ default: m.Story })));

const TITLES: Record<string, string> = {
  home: 'Agent Readiness — usability testing for AI agents',
  demo: 'Earlier case study: Ironbark Hire · Agent Readiness',
  run: 'Evaluation workspace · Agent Readiness',
  lifecycle: 'The Larkspur journey: evaluate, improve, re-evaluate · Agent Readiness',
  report: 'Readiness report · Agent Readiness',
  studio: 'Replay archive · Agent Readiness',
  showcase: 'Polished Larkspur: built for people, tested by agents · Agent Readiness',
  classic: 'Investigation archive · Agent Readiness',
};

export default function App() {
  const route = useRoute();
  const journey = route.name === 'demo' && !route.scene;
  useEffect(() => { document.title = TITLES[journey ? 'lifecycle' : route.name]; }, [route.name, journey]);
  // Each route starts at the top unless it targets a section/scene; those components scroll themselves.
  useEffect(() => {
    const targeted = (route.name === 'home' && route.section) || (route.name === 'demo' && route.scene) || (route.name === 'lifecycle' && route.step);
    if (!targeted) window.scrollTo?.({ top: 0 });
  }, [route.name, route.name === 'report' ? `${route.id}/${route.task ?? ''}` : '']);

  const fallback = <div className="ar route-loading" aria-busy="true"><p className="sr-only">Loading…</p></div>;
  switch (route.name) {
    case 'home': return <Home section={route.section} />;
    case 'run': return <Workspace job={route.job} />;
    case 'lifecycle': return <Lifecycle step={route.step} suite={route.suite} />;
    case 'report': return <ReportPage id={route.id} task={route.task} />;
    case 'showcase': return <Suspense fallback={<div className="ar ar-night route-loading" aria-busy="true"><p className="sr-only">Loading the showcase…</p></div>}><Story /></Suspense>;
    case 'demo': if (journey) return <Lifecycle />;
      return <Suspense fallback={<div className="ar ar-night route-loading" aria-busy="true"><p className="sr-only">Loading the demo…</p></div>}><Demo scene={route.scene === 'ironbark' ? undefined : route.scene} /></Suspense>;
    default: return <Suspense fallback={fallback}><Classic /></Suspense>;
  }
}
