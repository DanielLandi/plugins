import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { wireSoundButton } from './sound-button';

const fakeButton = () => {
  let onClick: () => void = () => {};
  const button = {
    textContent: '♪ Sound on' as string | null,
    disabled: false,
    hidden: true,
    addEventListener: (_type: 'click', fn: () => void) => { onClick = fn; },
  };
  return { button, click: () => onClick() };
};

const fakeSound = (results: Array<boolean | Error>) => {
  let started = false;
  return {
    get started() { return started; },
    toggle: vi.fn(async () => {
      const r = results.shift();
      if (r instanceof Error) throw r;
      started = true;
      return r ?? false;
    }),
  };
};

describe('wireSoundButton', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('shows itself and says what a click will do', async () => {
    const { button, click } = fakeButton();
    wireSoundButton(button, fakeSound([true, false]), () => {});
    expect(button.hidden).toBe(false);
    click();
    expect(button).toMatchObject({ textContent: '♪ Loading…', disabled: true });
    await vi.advanceTimersByTimeAsync(0);
    expect(button).toMatchObject({ textContent: '♪ Sound off', disabled: false });
    click();
    await vi.advanceTimersByTimeAsync(0);
    expect(button.textContent).toBe('♪ Sound on');
  });

  it('says when the sound is unavailable, then offers it again', async () => {
    const { button, click } = fakeButton();
    wireSoundButton(button, fakeSound([new Error('HTTP 404')]), () => {});
    click();
    await vi.advanceTimersByTimeAsync(0);
    expect(button).toMatchObject({ textContent: '♪ Sound unavailable', disabled: false });
    await vi.advanceTimersByTimeAsync(4000);
    expect(button.textContent).toBe('♪ Sound on');
  });

  it('keeps the label true when a retry inside those 4 s works', async () => {
    const { button, click } = fakeButton();
    wireSoundButton(button, fakeSound([new Error('HTTP 503'), true]), () => {});
    click();
    await vi.advanceTimersByTimeAsync(0);
    click();
    await vi.advanceTimersByTimeAsync(0);
    expect(button.textContent).toBe('♪ Sound off');
    await vi.advanceTimersByTimeAsync(4000);
    expect(button.textContent).toBe('♪ Sound off');
  });
});
