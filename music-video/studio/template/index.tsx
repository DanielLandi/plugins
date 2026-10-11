import React from 'react';
import { Composition } from 'remotion';
import {
  Excerpt, LyricLayer, SafeArea, Series, SongAudio, songMetadata, SongProvider,
  type LyricMode, type SongData, type SongProps,
} from '@mv/kit';
import { cuts } from './cuts';
import { lyricStyle, palette, subtitles, verticalSubtitles } from './look';
import { scenes } from './scenes';
import { ranges } from './video';

const ID = '__ID__';
const TITLE = '__ID__';

type Props = SongProps & { lyrics?: LyricMode };

const Video: React.FC<{ data: SongData; lyrics: LyricMode }> = ({ data, lyrics }) => (
  <SongProvider data={data}>
    <Series scenes={scenes} cuts={cuts} />
    <LyricLayer mode={lyrics} style={lyricStyle} />
    <SongAudio />
  </SongProvider>
);

const Full: React.FC<Props> = ({ data, lyrics }) => (data ? <Video data={data} lyrics={lyrics ?? subtitles} /> : null);

const Sample: React.FC<Props> = ({ data, lyrics }) =>
  data ? <Excerpt from={ranges.sample.from}><Video data={data} lyrics={lyrics ?? subtitles} /></Excerpt> : null;

const Vertical: React.FC<Props> = ({ data, lyrics }) =>
  data ? <Excerpt from={ranges.vertical.from}><Video data={data} lyrics={lyrics ?? verticalSubtitles} /></Excerpt> : null;

const Thumb: React.FC<Props> = ({ data }) =>
  data ? (
    <>
      <Video data={data} lyrics="none" />
      <SafeArea style={{ display: 'flex', alignItems: 'flex-end', color: palette.neutral, fontFamily: lyricStyle.fontFamily,
        fontWeight: 800, fontSize: 96, textShadow: '0 4px 24px rgba(0,0,0,0.7)' }}>
        {TITLE}
      </SafeArea>
    </>
  ) : null;

const common = { fps: 30, durationInFrames: 1, defaultProps: { data: null } as Props };

export const Compositions: React.FC = () => (
  <>
    <Composition id={`${ID}-full`} component={Full} width={1920} height={1080} {...common} calculateMetadata={songMetadata<Props>()} />
    <Composition id={`${ID}-sample`} component={Sample} width={1920} height={1080} {...common} calculateMetadata={songMetadata<Props>(ranges.sample)} />
    <Composition id={`${ID}-vertical`} component={Vertical} width={1080} height={1920} {...common} calculateMetadata={songMetadata<Props>(ranges.vertical)} />
    <Composition id={`${ID}-thumb`} component={Thumb} width={1280} height={720} {...common} calculateMetadata={songMetadata<Props>()} />
  </>
);
