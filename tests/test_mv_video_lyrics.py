from musicvideo.video.lyrics import is_section_tag, parse_lyrics

SONG = """[Piano Intro]

[Verse 1]
Paper lanterns swinging over a quiet street
Somebody whistles an old tune off the beat

[Pre-Chorus]
Windows open one by one

[Chorus]
Sing it to the morning

[Instrumental Break]

[Final Chorus]
Sing it to the morning

[Outro]
Sing to the morning
(Sing to the morning)
"""


def test_sections_keep_order_repeats_and_wordless_tags():
    lyrics = parse_lyrics(SONG)
    assert lyrics.sections == ("Piano Intro", "Verse 1", "Pre-Chorus", "Chorus",
                               "Instrumental Break", "Final Chorus", "Outro")
    assert [line.section for line in lyrics.lines] == [1, 1, 2, 3, 5, 6, 6]


def test_backing_line_keeps_parentheses_in_text_but_not_in_words():
    line = parse_lyrics(SONG).lines[-1]
    assert line.text == "(Sing to the morning)"
    assert line.words == ("Sing", "to", "the", "morning")
    assert line.backing == (True, True, True, True)


def test_mixed_line_marks_only_the_parenthesised_words():
    line = parse_lyrics("[Chorus]\nO vento levou a minha canção (levou a canção)\n").lines[0]
    assert line.words == ("O", "vento", "levou", "a", "minha", "canção", "levou", "a", "canção")
    assert line.backing == (False,) * 6 + (True,) * 3


def test_performance_tags_are_stripped_and_do_not_start_sections():
    lyrics = parse_lyrics("[Verse 1]\n[Whispered] hold on\n[Breath]\nlet go [Belted]\n")
    assert lyrics.sections == ("Verse 1",)
    assert [line.text for line in lyrics.lines] == ["hold on", "let go"]


def test_words_before_any_tag_get_an_intro_section():
    lyrics = parse_lyrics("la la\n[Verse]\nhello there\n")
    assert lyrics.sections == ("Intro", "Verse")
    assert [line.section for line in lyrics.lines] == [0, 1]


def test_alignment_text_and_word_list_keep_punctuation_and_accents():
    lyrics = parse_lyrics("[Intro]\nÔ-ô-ô, laiá\n(Ônibus)\n")
    assert lyrics.alignment_text() == "Ô-ô-ô, laiá\nÔnibus"
    assert lyrics.words == ["Ô-ô-ô,", "laiá", "Ônibus"]


def test_is_section_tag():
    for tag in ("Pre-Chorus", "Piano Intro", "Instrumental Break", "Final Chorus", "Drop"):
        assert is_section_tag(tag), tag
    for tag in ("Breath", "Whispered", "Harmonies", "Belted", "Build"):
        assert not is_section_tag(tag), tag
