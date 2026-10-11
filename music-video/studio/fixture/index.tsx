import React from 'react';
import { Composition } from 'remotion';
import { Excerpt, LyricLayer, Series, SongAudio, songMetadata, SongProvider, type LyricStyle, type SongProps } from '@mv/kit';
import { cuts } from './cuts';
import { scenes } from './scenes';

const style: LyricStyle = { fontFamily: 'Helvetica, Arial, sans-serif', size: 0.07, color: '#ffffff', highlight: '#f5c542',
  position: 'bottom' };

const Main: React.FC<SongProps> = ({ data }) =>
  data ? (
    <SongProvider data={data}>
      <Series scenes={scenes} cuts={cuts} />
      <LyricLayer mode="words" style={style} />
      <SongAudio />
    </SongProvider>
  ) : null;

const Vertical: React.FC<SongProps> = (props) => (
  <Excerpt from={1}>
    <Main {...props} />
  </Excerpt>
);

export const Compositions: React.FC = () => (
  <>
    <Composition id="fixture-full" component={Main} width={1920} height={1080} fps={30} durationInFrames={1}
      defaultProps={{ data: null }} calculateMetadata={songMetadata<SongProps>()} />
    <Composition id="fixture-vertical" component={Vertical} width={1080} height={1920} fps={30} durationInFrames={1}
      defaultProps={{ data: null }} calculateMetadata={songMetadata<SongProps>({ from: 1, to: 3 })} />
  </>
);
