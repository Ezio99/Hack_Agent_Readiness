import { lazy, Suspense, useEffect } from 'react';
import { useRoute } from './site/router';
import { Home } from './site/Home';
import { Workspace } from './site/workspace/Workspace';
import { Lifecycle } from './site/lifecycle/Lifecycle';
import { ReportPage } from './site/lifecycle/Report';

/** The cinematic demo carries its own evidence frames; the archive carries the pre-redesign app. Both load on demand. */
const Demo = lazy(() => import('./site/demo/Demo').then(m => ({ default: m.Demo })));
const Classic = lazy(() => import('./legacy/Classic'));

const TITLES: Record<string, string> = {
  home: 'Agent Readiness — usability testing for AI agents',
  demo: 'Demo — watch an AI agent use a website · Agent Readiness',
  run: 'Evaluation workspace · Agent Readiness',
  lifecycle: 'Evaluation lifecycle · Agent Readiness',
  report: 'Readiness report · Agent Readiness',
  studio: 'Replay archive · Agent Readiness',
  classic: 'Investigation archive · Agent Readiness',
};

export default function App() {
  const route = useRoute();
  useEffect(() => { document.title = TITLES[route.name]; }, [route.name]);
  // Each route starts at the top unless it targets a section/scene; those components scroll themselves.
  useEffect(() => {
    const targeted = (route.name === 'home' && route.section) || (route.name === 'demo' && route.scene);
    if (!targeted) window.scrollTo?.({ top: 0 });
  }, [route.name, route.name === 'report' ? `${route.id}/${route.task ?? ''}` : '']);

  const fallback = <div className="ar route-loading" aria-busy="true"><p className="sr-only">Loading…</p></div>;
  switch (route.name) {
    case 'home': return <Home section={route.section} />;
    case 'run': return <Workspace job={route.job} />;
    case 'lifecycle': return <Lifecycle step={route.step} suite={route.suite} job={route.job} />;
    case 'report': return <ReportPage id={route.id} task={route.task} />;
    case 'demo': return <Suspense fallback={<div className="ar ar-night route-loading" aria-busy="true"><p className="sr-only">Loading the demo…</p></div>}><Demo scene={route.scene} /></Suspense>;
    default: return <Suspense fallback={fallback}><Classic /></Suspense>;
  }
}
