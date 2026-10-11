import React from 'react';
import { LyricLayer, Series, SongProvider, type SongProps, type WebEntry } from '@mv/kit';
import { cuts } from './cuts';
import { scenes } from './scenes';

const Page: React.FC<SongProps> = ({ data }) =>
  data ? (
    <SongProvider data={data}>
      <Series scenes={scenes} cuts={cuts} />
      <LyricLayer mode="lines" style={{ fontFamily: 'Helvetica, Arial, sans-serif', size: 0.07, color: '#ffffff',
        highlight: '#f5c542', position: 'bottom' }} />
    </SongProvider>
  ) : null;

export const web: WebEntry = { Component: Page, fps: 30, frames: (data) => data.analysis.duration * 30 };
