import pytest

from musicvideo.video.onsets import first_sound


@pytest.mark.parametrize("word,kind", [
    ("sunlight", "fricative"), ("shine", "fricative"), ("Charlie", "fricative"), ("photo", "fricative"),
    ("the", "fricative"), ("very", "fricative"), ("zero", "fricative"), ("city", "fricative"), ("gentle", "fricative"),
    ("jump", "fricative"), ("xylophone", "fricative"),
    ("paper", "stop"), ("better", "stop"), ("time", "stop"), ("door", "stop"), ("kite", "stop"), ("car", "stop"),
    ("queen", "stop"), ("go", "stop"),
    ("moon", "voiced"), ("night", "voiced"), ("love", "voiced"), ("road", "voiced"), ("we", "voiced"),
    ("you", "voiced"), ("open", "voiced"), ("home", "voiced"),
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
