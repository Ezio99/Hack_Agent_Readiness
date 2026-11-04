import { AbsoluteFill, Audio, Composition, continueRender, delayRender, Sequence, Series, staticFile } from 'remotion';
import { ACT1, ACT2, ACT3, ACT4, ACT5, type Act } from './narration';
import { Act2, ACT2_FRAMES } from './scenes/Act2';
import { Act3, ACT3_FRAMES } from './scenes/Act3';
import { Act4, ACT4_FRAMES } from './scenes/Act4';
import { Act5, ACT5_FRAMES } from './scenes/Act5';
import { Opening, OPENING_FRAMES } from './scenes/Opening';
import { fontsReady } from './theme/fonts';
import { AuditionLabel, auditionFile, auditionLines, EXCERPTS, excerptFrames, musicVolume, ScratchMark, Voice, VOICES } from './Voice';

const wait = delayRender('fonts');
fontsReady.then(() => continueRender(wait));

/** Film-time offset of each act (frames): the music track is one continuous score; an act rendered alone plays its slice of it. */
const OFFSET = { act1: 0, act2: OPENING_FRAMES, act3: OPENING_FRAMES + ACT2_FRAMES, act4: OPENING_FRAMES + ACT2_FRAMES + ACT3_FRAMES,
  act5: OPENING_FRAMES + ACT2_FRAMES + ACT3_FRAMES + ACT4_FRAMES } as const;
const TOTAL = OFFSET.act5 + ACT5_FRAMES;

/** Three separate tracks: music (one continuous score, ducked under the voice), sound effects (placed inside the scenes at recorded events) and
 *  voiceover (one file per act, each line placed by the cue sheet). Placeholder acts render without voice; their captions show the planned lines. */
function Tracks({ from, acts, sfxOnly = false }: { from: number; acts: Act[]; sfxOnly?: boolean }) {
  if (sfxOnly) return null;   // the offline mixdown (scripts/mixdown.mjs) renders this composition's SFX alone, then adds music and voice sample-accurately
  const spoken: [number, number][] = [];
  { let o = 0; for (const a of acts) { if (a.status === 'recorded') for (const l of a.lines) spoken.push([o + l.at, o + l.end]); o += a.frames; } }
  let at = 0;
  return <>
    <Audio src={staticFile('audio/music/score.wav')} startFrom={from} volume={musicVolume(spoken)} />
    {acts.map(a => { const start = at; at += a.frames;
      return a.status === 'recorded' ? <Sequence key={a.id} from={start} durationInFrames={a.frames} layout="none"><Voice lines={a.lines} file={a.vo} /></Sequence> : null; })}
    {acts.some(a => a.source === 'scratch') && <ScratchMark />}
  </>;
}

/** A voice audition: the candidate's three clips, each under the picture it belongs to, with the film's music and mix. */
const Audition = ({ voice }: { voice: string }) => { let at = 0;
  const scene = { act1: Opening, act2: Act2, act5: Act5 } as Record<string, (p: { captions?: boolean }) => React.ReactNode>;
  return <AbsoluteFill style={{ background: '#000' }}>{EXCERPTS.map(e => { const start = at, len = excerptFrames(e); at += len;
    const S = scene[e.act.id], lines = auditionLines(voice, e), file = auditionFile(voice, e.n);
    return <Sequence key={e.n} from={start} durationInFrames={len}>
      <Sequence from={-e.start} layout="none"><S captions={false} /></Sequence>
      <Audio src={staticFile('audio/music/score.wav')} startFrom={OFFSET[e.act.id as keyof typeof OFFSET] + e.start} volume={musicVolume(lines.map(l => [l.at, l.end]))} />
      {file && <Voice lines={lines} file={file} />}
      <AuditionLabel voice={voice} label={file ? e.label : e.label + ' · no clip'} />
    </Sequence>; })}</AbsoluteFill>; };
const AUDITION_FRAMES = EXCERPTS.reduce((s, e) => s + excerptFrames(e), 0);

const ActOne = ({ captions }: { captions: boolean }) => <AbsoluteFill><Opening captions={captions} /><Tracks from={OFFSET.act1} acts={[ACT1]} /></AbsoluteFill>;
const ActThree = ({ captions }: { captions: boolean }) => <AbsoluteFill><Act3 captions={captions} /><Tracks from={OFFSET.act3} acts={[ACT3]} /></AbsoluteFill>;
const ActFour = ({ captions }: { captions: boolean }) => <AbsoluteFill><Act4 captions={captions} /><Tracks from={OFFSET.act4} acts={[ACT4]} /></AbsoluteFill>;
const ActFive = ({ captions }: { captions: boolean }) => <AbsoluteFill><Act5 captions={captions} /><Tracks from={OFFSET.act5} acts={[ACT5]} /></AbsoluteFill>;
const ActTwo = ({ captions }: { captions: boolean }) => <AbsoluteFill><Act2 captions={captions} /><Tracks from={OFFSET.act2} acts={[ACT2]} /></AbsoluteFill>;
const Preview = ({ captions, sfxOnly = false }: { captions: boolean; sfxOnly?: boolean }) => <AbsoluteFill>
  <Series>
    <Series.Sequence durationInFrames={OPENING_FRAMES}><Opening captions={captions} /></Series.Sequence>
    <Series.Sequence durationInFrames={ACT2_FRAMES}><Act2 captions={captions} /></Series.Sequence>
    <Series.Sequence durationInFrames={ACT3_FRAMES}><Act3 captions={captions} /></Series.Sequence>
    <Series.Sequence durationInFrames={ACT4_FRAMES}><Act4 captions={captions} /></Series.Sequence>
    <Series.Sequence durationInFrames={ACT5_FRAMES}><Act5 captions={captions} /></Series.Sequence>
  </Series>
  <Tracks from={0} acts={[ACT1, ACT2, ACT3, ACT4, ACT5]} sfxOnly={sfxOnly} />
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
    <Composition id="Act4" component={ActFour} durationInFrames={ACT4_FRAMES} {...v} defaultProps={{ captions: false }} />
    <Composition id="Act4Captions" component={ActFour} durationInFrames={ACT4_FRAMES} {...v} defaultProps={{ captions: true }} />
    <Composition id="Act5" component={ActFive} durationInFrames={ACT5_FRAMES} {...v} defaultProps={{ captions: false }} />
    <Composition id="Act5Captions" component={ActFive} durationInFrames={ACT5_FRAMES} {...v} defaultProps={{ captions: true }} />
    <Composition id="Preview" component={Preview} durationInFrames={TOTAL} {...v} defaultProps={{ captions: false }} />
    <Composition id="PreviewCaptions" component={Preview} durationInFrames={TOTAL} {...v} defaultProps={{ captions: true }} />
    <Composition id="Audition" component={Audition} durationInFrames={AUDITION_FRAMES} {...v} defaultProps={{ voice: VOICES[0] ?? 'dan' }} />
  </>;
}
