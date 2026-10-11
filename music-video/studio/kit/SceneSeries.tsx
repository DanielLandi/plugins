import React from 'react';
import { Sequence, useVideoConfig } from 'remotion';
import { linearTiming, TransitionSeries } from '@remotion/transitions';
import { layoutSeries, type CutSpec, type SceneSpec } from './series';
import { useSongData } from './SongContext';
import { transitionPresentation } from './transitions';

export type SceneEntry = SceneSpec & { Component: React.FC };

/** The whole song as scenes joined by the cut list; inside every scene, useSongTime() is song time. */
export const Series: React.FC<{ scenes: readonly SceneEntry[]; cuts: readonly CutSpec[] }> = ({ scenes, cuts }) => {
  const { analysis } = useSongData();
  const { fps } = useVideoConfig();
  const layout = layoutSeries(scenes, cuts, analysis.duration, fps);
  const children: React.ReactNode[] = [];
  layout.scenes.forEach((slot, i) => {
    const { Component } = scenes[i];
    children.push(
      <TransitionSeries.Sequence key={`scene-${slot.id}`} durationInFrames={slot.durationInFrames}>
        <Sequence from={-slot.startFrame}>
          <Component />
        </Sequence>
      </TransitionSeries.Sequence>,
    );
    const next = layout.cuts[i];
    if (next) {
      children.push(
        <TransitionSeries.Transition key={`cut-${i}`} presentation={transitionPresentation(next.cut.transition, next.cut.params)}
          timing={linearTiming({ durationInFrames: next.cut.frames })} />,
      );
    }
  });
  return <TransitionSeries>{children}</TransitionSeries>;
};
