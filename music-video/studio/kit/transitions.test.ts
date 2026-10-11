import { describe, expect, it } from 'vitest';
import { transitionIds, transitionMeta, transitionPresentation } from './transitions';

describe('vendored transitions', () => {
  it('lists the library', () => {
    expect(transitionIds).toHaveLength(50);
    expect(transitionMeta('iris').family).toBe('03-wipe');
  });
  it('merges params over the defaults', () => {
    expect(transitionPresentation('iris', { y: 0.2 }).props).toMatchObject({ x: 0.5, y: 0.2, softness: 0 });
  });
  it('names the known ids when one is wrong', () => {
    expect(() => transitionMeta('nope')).toThrow(/Unknown transition "nope". Known: .*iris/);
  });
});
