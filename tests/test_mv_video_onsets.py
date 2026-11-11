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
