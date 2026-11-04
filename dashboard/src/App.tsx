import { lazy, Suspense, useEffect } from 'react';
import { useRoute } from './site/router';
import { Home } from './site/Home';
import { Workspace } from './site/workspace/Workspace';
import { Lifecycle } from './site/lifecycle/Lifecycle';
import { ReportPage } from './site/lifecycle/Report';

/** `#/demo` is the Larkspur journey (the same page as `#/lifecycle`). Earlier case studies and archives are not part of the public app. */
const Story = lazy(() => import('./site/story/Story').then(m => ({ default: m.Story })));

const TITLES: Record<string, string> = {
  home: 'Agent Readiness — usability testing for AI agents',
  run: 'Evaluation workspace · Agent Readiness',
  lifecycle: 'The Larkspur journey: evaluate, improve, re-evaluate · Agent Readiness',
  report: 'Readiness report · Agent Readiness',
  showcase: 'Larkspur Community College: before and after · Agent Readiness',
};

export default function App() {
  const route = useRoute();
  const journey = route.name === 'demo';
  useEffect(() => { document.title = TITLES[journey ? 'lifecycle' : route.name]; }, [route.name, journey]);
  // Each route starts at the top unless it targets a section/scene; those components scroll themselves.
  useEffect(() => {
    const targeted = (route.name === 'home' && route.section) || (route.name === 'lifecycle' && route.step);
    if (!targeted) window.scrollTo?.({ top: 0 });
  }, [route.name, route.name === 'report' ? `${route.id}/${route.task ?? ''}` : '']);

  switch (route.name) {
    case 'home': return <Home section={route.section} />;
    case 'run': return <Workspace job={route.job} />;
    case 'lifecycle': return <Lifecycle step={route.step} suite={route.suite} />;
    case 'report': return <ReportPage id={route.id} task={route.task} />;
    case 'showcase': return <Suspense fallback={<div className="ar ar-night route-loading" aria-busy="true"><p className="sr-only">Loading the showcase…</p></div>}><Story /></Suspense>;
    case 'demo': return <Lifecycle />;
    default: return <Home />;
  }
}
