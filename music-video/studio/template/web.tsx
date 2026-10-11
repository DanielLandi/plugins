// The live web page of this video (`music-video web __ID__`): what the page plays, on a loop, in the browser.
// By default the whole video with its subtitles; to loop a stretch instead, see kit/loop.ts (loopLayout,
// seamOpacity) and set `words` to the only sung words the page should keep.
import React from 'react';
import { LyricLayer, Series, SongProvider, type SongProps, type WebEntry } from '@mv/kit';
import { cuts } from './cuts';
import { lyricStyle, subtitles } from './look';
import { scenes } from './scenes';

const Page: React.FC<SongProps> = ({ data }) =>
  data ? (
    <SongProvider data={data}>
      <Series scenes={scenes} cuts={cuts} />
      <LyricLayer mode={subtitles} style={lyricStyle} />
    </SongProvider>
  ) : null;

export const web: WebEntry = { Component: Page, fps: 30, frames: (data) => data.analysis.duration * 30 };
