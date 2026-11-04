import { AbsoluteFill, Audio, Composition, continueRender, delayRender, Sequence, Series, staticFile } from 'remotion';
import { ACT1, ACT2, ACT3, type Act } from './narration';
import { Act2, ACT2_FRAMES } from './scenes/Act2';
import { Act3, ACT3_FRAMES } from './scenes/Act3';
import { Opening, OPENING_FRAMES } from './scenes/Opening';
import { fontsReady } from './theme/fonts';

const wait = delayRender('fonts');
fontsReady.then(() => continueRender(wait));

/** Film-time offset of each act (frames): the music track is one continuous score; an act rendered alone plays its slice of it. */
const OFFSET = { act1: 0, act2: OPENING_FRAMES, act3: OPENING_FRAMES + ACT2_FRAMES } as const;
const TOTAL = OPENING_FRAMES + ACT2_FRAMES + ACT3_FRAMES;

/** Three separate tracks: music (one continuous score), sound effects (placed inside the scenes at recorded events) and voiceover (one file per
 *  act, only once recorded: placeholder acts render without voice; their captions version shows the planned lines). */
function Tracks({ from, acts }: { from: number; acts: Act[] }) {
  let at = 0;
  return <>
    <Audio src={staticFile('audio/music/score.wav')} startFrom={from} volume={0.55} />
    {acts.map(a => { const start = at; at += a.frames;
      return a.status === 'recorded' ? <Sequence key={a.id} from={start} durationInFrames={a.frames}><Audio src={staticFile(a.vo)} /></Sequence> : null; })}
  </>;
}

const ActOne = ({ captions }: { captions: boolean }) => <AbsoluteFill><Opening captions={captions} /><Tracks from={OFFSET.act1} acts={[ACT1]} /></AbsoluteFill>;
const ActThree = ({ captions }: { captions: boolean }) => <AbsoluteFill><Act3 captions={captions} /><Tracks from={OFFSET.act3} acts={[ACT3]} /></AbsoluteFill>;
const ActTwo = ({ captions }: { captions: boolean }) => <AbsoluteFill><Act2 captions={captions} /><Tracks from={OFFSET.act2} acts={[ACT2]} /></AbsoluteFill>;
const Preview = ({ captions }: { captions: boolean }) => <AbsoluteFill>
  <Series>
    <Series.Sequence durationInFrames={OPENING_FRAMES}><Opening captions={captions} /></Series.Sequence>
    <Series.Sequence durationInFrames={ACT2_FRAMES}><Act2 captions={captions} /></Series.Sequence>
    <Series.Sequence durationInFrames={ACT3_FRAMES}><Act3 captions={captions} /></Series.Sequence>
  </Series>
  <Tracks from={0} acts={[ACT1, ACT2, ACT3]} />
</AbsoluteFill>;

const v = { fps: 30, width: 1920, height: 1080 } as const;
/** One composition per act (rendered and reviewed separately), each with a captions variant, plus the running preview of the film so far. */
export function Root() {
  return <>
    <Composition id="Opening" component={ActOne} durationInFrames={OPENING_FRAMES} {...v} defaultProps={{ captions: false }} />
    <Composition id="OpeningCaptions" component={ActOne} durationInFrames={OPENING_FRAMES} {...v} defaultProps={{ captions: true }} />
    <Composition id="Act2" component={ActTwo} durationInFrames={ACT2_FRAMES} {...v} defaultProps={{ captions: false }} />
    <Composition id="Act2Captions" component={ActTwo} durationInFrames={ACT2_FRAMES} {...v} defaultProps={{ captions: true }} />
    <Composition id="Act3" component={ActThree} durationInFrames={ACT3_FRAMES} {...v} defaultProps={{ captions: false }} />
    <Composition id="Act3Captions" component={ActThree} durationInFrames={ACT3_FRAMES} {...v} defaultProps={{ captions: true }} />
    <Composition id="Preview" component={Preview} durationInFrames={TOTAL} {...v} defaultProps={{ captions: false }} />
    <Composition id="PreviewCaptions" component={Preview} durationInFrames={TOTAL} {...v} defaultProps={{ captions: true }} />
  </>;
}
