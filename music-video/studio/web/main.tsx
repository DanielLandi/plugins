import React, { useEffect, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Player, type PlayerRef } from '@remotion/player';
import { webFrames, type SongData, type WebEntry } from '@mv/kit';
import { web } from '@mv/web-entry';
import { compositionSize } from './shape';
import { createSound, type AudioMeta } from './sound';
import { wireSoundButton } from './sound-button';
import { startStats } from './stats';
// The video's own page styles (web/styles.css in its folder, e.g. self-hosted fonts), or nothing.
import '@mv/web-styles';
import scoreUrl from './.data/score.json?url';

// score.json: the song data the page draws from, and the audio loop's timing when the page has sound.
type Score = { data: SongData; audio: (AudioMeta & { file: string }) | null };

const params = new URLSearchParams(location.search);

const useWindowShape = () => {
  const read = () => compositionSize(window.innerWidth, window.innerHeight);
  const [size, setSize] = useState(read);
  useEffect(() => {
    let timer = 0;
    const onResize = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => setSize(read()), 250);
    };
    window.addEventListener('resize', onResize);
    return () => {
      window.clearTimeout(timer);
      window.removeEventListener('resize', onResize);
    };
  }, []);
  return size;
};

const Stage: React.FC<{ entry: WebEntry; data: SongData }> = ({ entry, data }) => {
  const { width, height } = useWindowShape();
  const ref = useRef<PlayerRef>(null);
  const frames = webFrames(entry, data);
  useEffect(() => {
    const player = ref.current;
    if (!player) return;
    // ?at=<seconds into the loop>, for checking a stretch by eye; ?stats, to measure drawing speed.
    const at = Number(params.get('at'));
    if (at > 0) player.seekTo(Math.round(at * entry.fps) % frames);
    if (params.has('stats')) startStats(player);
  }, [entry, frames]);
  return (
    <Player ref={ref} component={entry.Component} inputProps={{ data }} durationInFrames={frames} fps={entry.fps}
      compositionWidth={width} compositionHeight={height} style={{ width: '100%', height: '100%' }}
      loop autoPlay initiallyMuted controls={false} clickToPlay={false} doubleClickToFullscreen={false}
      spaceKeyToPlayOrPause={false} numberOfSharedAudioTags={0} acknowledgeRemotionLicense />
  );
};

const wireSound = (meta: AudioMeta & { file: string }) => {
  // The audio loop is a content-hashed asset (assets/loop-<hash>.m4a), so a cached old one is never played.
  const sound = createSound(new URL(meta.file, document.baseURI).href, meta);
  wireSoundButton(document.getElementById('sound') as HTMLButtonElement, sound);
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') sound.wake();
  });
};

const boot = async () => {
  const res = await fetch(scoreUrl);
  if (!res.ok) throw new Error(`score.json: HTTP ${res.status}`);
  const score = (await res.json()) as Score;
  createRoot(document.getElementById('stage')!).render(<Stage entry={web} data={score.data} />);
  if (score.audio) wireSound(score.audio);
};

boot().catch((e) => {
  console.error(e);
  document.getElementById('stage')!.textContent = 'The animation could not load.';
});
