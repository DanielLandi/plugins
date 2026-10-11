/** The parts of the button and of createSound() the wiring needs (tested with fakes). */
export type ButtonLike = {
  textContent: string | null;
  disabled: boolean;
  hidden: boolean;
  addEventListener(type: 'click', listener: () => void): void;
};
export type SoundLike = { readonly started: boolean; toggle(): Promise<boolean> };

/** How long "Sound unavailable" stays before the button offers the sound again. */
const UNAVAILABLE_MS = 4000;

/**
 * The sound button. Its label is what a click will do ("Sound on" / "Sound off"), so it carries no aria-pressed:
 * a screen reader would otherwise hear "Sound off, pressed".
 */
export const wireSoundButton = (button: ButtonLike, sound: SoundLike, log: (e: unknown) => void = console.error) => {
  let reset: ReturnType<typeof setTimeout> | undefined;
  const show = (label: string, disabled = false) => {
    button.textContent = label;
    button.disabled = disabled;
  };
  button.hidden = false;
  button.addEventListener('click', () => {
    clearTimeout(reset);
    if (!sound.started) show('♪ Loading…', true);
    sound.toggle().then(
      (on) => show(on ? '♪ Sound off' : '♪ Sound on'),
      (e) => {
        log(e);
        show('♪ Sound unavailable');
        reset = setTimeout(() => show('♪ Sound on'), UNAVAILABLE_MS);
      },
    );
  });
};
