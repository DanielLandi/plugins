// flubber 0.4.2 (MIT) ships no types: the one function the cartoon engine uses (kit/cartoon/rig.ts).
declare module 'flubber' {
  type Ring = [number, number][];
  export function interpolate(
    from: Ring | string, to: Ring | string,
    options?: { string?: boolean; maxSegmentLength?: number | false },
  ): (t: number) => Ring | string;
}
