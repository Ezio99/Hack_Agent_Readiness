import { Composition, continueRender, delayRender } from 'remotion';
import { Opening, OPENING_FRAMES } from './scenes/Opening';
import { fontsReady } from './theme/fonts';

const wait = delayRender('fonts');
fontsReady.then(() => continueRender(wait));

/** One composition per act (rendered and reviewed separately); the full film will chain them. Only the opening exists so far. */
export function Root() {
  return <>
    <Composition id="Opening" component={Opening} durationInFrames={OPENING_FRAMES} fps={30} width={1920} height={1080} defaultProps={{ captions: false }} />
    <Composition id="OpeningCaptions" component={Opening} durationInFrames={OPENING_FRAMES} fps={30} width={1920} height={1080} defaultProps={{ captions: true }} />
  </>;
}
