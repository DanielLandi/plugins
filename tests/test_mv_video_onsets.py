import pytest

from musicvideo.video.onsets import first_sound


@pytest.mark.parametrize("word,kind", [
    ("sunlight", "fricative"), ("shine", "fricative"), ("Charlie", "fricative"), ("photo", "fricative"),
    ("thin", "fricative"), ("very", "fricative"), ("zero", "fricative"), ("city", "fricative"), ("gentle", "fricative"),
    ("jump", "fricative"), ("xylophone", "fricative"),
    ("paper", "stop"), ("better", "stop"), ("time", "stop"), ("door", "stop"), ("kite", "stop"), ("car", "stop"),
    ("queen", "stop"), ("go", "stop"),
    ("moon", "voiced"), ("night", "voiced"), ("love", "voiced"), ("road", "voiced"), ("we", "voiced"),
    ("you", "voiced"), ("open", "voiced"), ("home", "voiced"), ("the", "voiced"), ("them", "voiced"), ("this", "voiced"),
])
def test_first_sound_english(word, kind):
    assert first_sound(word, "en") == kind


@pytest.mark.parametrize("word,kind", [
    ("saudade", "fricative"), ("Chão", "fricative"), ("céu", "fricative"), ("cinema", "fricative"),
    ("ça", "fricative"), ("rua", "fricative"), ("Rosa", "fricative"), ("gente", "fricative"), ("janela", "fricative"),
    ("casa", "stop"), ("gato", "stop"), ("quero", "stop"), ("pão", "stop"),
    ("mar", "voiced"), ("noite", "voiced"), ("lua", "voiced"), ("hoje", "voiced"), ("é", "voiced"),
    ("água", "voiced"), ("ontem", "voiced"),
])
def test_first_sound_portuguese(word, kind):
    assert first_sound(word, "pt") == kind


@pytest.mark.parametrize("word,lang,kind", [
    ("'cause", "en", "stop"), ("(oh)", "en", "voiced"), ("9-to-5", "en", "voiced"), ("¿sí", "es", "fricative"),
    ("Tag", "de", "stop"), ("Mond", "de", "voiced"), ("", "en", "voiced"), ("Saudade", "pt-BR", "fricative"),
])
def test_first_sound_odd_words(word, lang, kind):
    assert first_sound(word, lang) == kind


# ---------------------------------------------------------------- measuring on the vocal stem (synthetic audio)

import numpy as np

from musicvideo.video.onsets import ONSET_SR, measure_onset

RNG = np.random.default_rng(7)


def silence(s):
    return RNG.normal(0, 1e-4, int(s * ONSET_SR))


def tone(f, s, amp=0.3):
    t = np.arange(int(s * ONSET_SR)) / ONSET_SR
    return amp * (np.sin(2 * np.pi * f * t) + 0.5 * np.sin(4 * np.pi * f * t))


def noise(s, amp=0.1, hp=4000.0):
    x = RNG.normal(0, 1, int(s * ONSET_SR))
    spec = np.fft.rfft(x)
    spec[np.fft.rfftfreq(len(x), 1 / ONSET_SR) < hp] = 0
    y = np.fft.irfft(spec, len(x))
    return amp * y / (np.abs(y).max() or 1)


def click():
    return noise(0.005, amp=0.5, hp=0.0)


def cat(*parts):
    return np.concatenate(parts)


def test_a_hiss_starts_the_s_word():
    audio = cat(silence(0.5), noise(0.2), tone(220, 0.4))
    assert abs(0.70 - 0.50) > 0.15  # the aligner's guess (the vowel) is planted 0.20 s late
    t, conf = measure_onset(audio, ONSET_SR, lo=0.40, hi=0.95, guess=0.70, sound="fricative")
    assert t is not None and abs(t - 0.50) <= 0.01 and conf >= 0.5


def test_a_burst_starts_the_stop_word():
    audio = cat(silence(0.5), click(), silence(0.03), tone(220, 0.5))
    assert abs(0.60 - 0.50) > 0.05
    t, conf = measure_onset(audio, ONSET_SR, lo=0.30, hi=0.80, guess=0.60, sound="stop")
    assert t is not None and abs(t - 0.50) <= 0.01 and conf >= 0.5


def test_a_voiced_word_starts_on_the_voice_not_the_breath():
    audio = cat(silence(0.45), noise(0.15, amp=0.02, hp=0.0), tone(220, 0.5))
    assert abs(0.50 - 0.60) > 0.05
    t, conf = measure_onset(audio, ONSET_SR, lo=0.35, hi=0.85, guess=0.50, sound="voiced")
    assert t is not None and abs(t - 0.60) <= 0.01 and conf >= 0.5


def test_a_voiced_word_after_a_dip():
    audio = cat(tone(330, 0.48), silence(0.04), tone(220, 0.5))
    assert abs(0.40 - 0.52) > 0.1
    t, conf = measure_onset(audio, ONSET_SR, lo=0.30, hi=0.80, guess=0.40, sound="voiced")
    assert t is not None and abs(t - 0.52) <= 0.01


@pytest.mark.parametrize("sound", ["fricative", "stop", "voiced"])
def test_no_clear_event_gives_no_onset(sound):
    for audio in (tone(440, 1.5), silence(1.5)):
        t, conf = measure_onset(audio, ONSET_SR, lo=0.3, hi=1.0, guess=0.6, sound=sound)
        assert t is None or conf < 0.5


# ---------------------------------------------------------------- refining the words

from musicvideo.video.onsets import refine_onsets
from musicvideo.video.timing import Word


def s_word_stem():
    """A hiss at 0.50 s, the vowel from 0.70 s."""
    return cat(silence(0.5), noise(0.2), tone(220, 0.6))


def test_refine_moves_an_s_word_onto_its_hiss():
    out = refine_onsets([Word("sun", 0.70, 1.0, 0.9)], s_word_stem(), ONSET_SR, "en", keep=set())
    w = out[0]
    assert abs(w.start - 0.50) <= 0.01 and w.end == 1.0
    assert (w.source, w.sound) == ("onset", "fricative") and abs(w.moved + 0.20) <= 0.01


def test_refine_skips_kept_words():
    w = refine_onsets([Word("sun", 0.70, 1.0, 0.9)], s_word_stem(), ONSET_SR, "en", keep={0})[0]
    assert (w.start, w.sound, w.moved, w.source) == (0.70, "fricative", 0.0, "align")


def test_refine_never_reaches_into_the_previous_word():
    words = [Word("a", 0.10, 0.62, 0.9), Word("sun", 0.70, 1.0, 0.9)]  # the hiss at 0.50 is under the previous word
    prev, w = refine_onsets(words, s_word_stem(), ONSET_SR, "en", keep=set())
    assert w.start >= 0.62 - 0.05


def test_refine_trims_the_previous_word():
    words = [Word("a", 0.10, 0.53, 0.9), Word("sun", 0.70, 1.0, 0.9)]
    prev, w = refine_onsets(words, s_word_stem(), ONSET_SR, "en", keep=set())
    assert abs(w.start - 0.50) <= 0.01 and prev.end == w.start


def test_refine_will_not_squeeze_the_previous_word():
    words = [Word("a", 0.46, 0.62, 0.9), Word("sun", 0.70, 1.0, 0.9)]
    prev, w = refine_onsets(words, s_word_stem(), ONSET_SR, "en", keep=set())
    assert (prev.end, w.start, w.moved) == (0.62, 0.70, 0.0)


def test_refine_never_goes_below_zero():
    audio = cat(noise(0.2), tone(220, 0.6))
    w = refine_onsets([Word("sun", 0.10, 0.6, 0.9)], audio, ONSET_SR, "en", keep=set())[0]
    assert w.start >= 0.0


def test_refine_keeps_the_start_without_a_clear_event():
    w = refine_onsets([Word("moon", 0.60, 1.0, 0.9)], tone(440, 1.5), ONSET_SR, "en", keep=set())[0]
    assert (w.start, w.moved) == (0.60, 0.0) and w.sound == "voiced"
