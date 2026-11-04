import { loadFont } from '@remotion/fonts';
import { staticFile } from 'remotion';
/** The product's OFL fonts (copied by scripts/capture.py from dashboard/src/site/fonts, licences alongside). */
export const fontsReady = Promise.all([
  loadFont({ family: 'AR Newsreader', url: staticFile('fonts/newsreader.woff2'), weight: '200 800', style: 'normal' }),
  loadFont({ family: 'AR Newsreader', url: staticFile('fonts/newsreader-italic.woff2'), weight: '200 800', style: 'italic' }),
  loadFont({ family: 'AR Geist', url: staticFile('fonts/geist.woff2'), weight: '100 900' }),
  loadFont({ family: 'AR Geist Mono', url: staticFile('fonts/geist-mono.woff2'), weight: '100 900' }),
]);
