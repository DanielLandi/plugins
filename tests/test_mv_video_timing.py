import numpy as np
import pytest

from musicvideo.errors import MVError
from musicvideo.video.lyrics import parse_lyrics
from musicvideo.video.timing import (Word, apply_fixes, build_timing, clock, line_ends, match_heard,
                                   missing_lines, norm, reconcile, show_words, snap_to_voice, suspects)


def W(text, start, end, conf=0.95, source="align"):
    return Word(text, start, end, conf, source)


def envelope(voiced, total_s=10.0, frame_s=0.02):
    env = np.full(int(total_s / frame_s), 0.001)
    for a, b in voiced:
        env[int(a / frame_s):int(b / frame_s)] = 1.0
    return env


def test_norm_folds_case_accents_and_punctuation():
    assert norm("Ônibus,") == "onibus"
    assert norm("Ô-ô-ô,") == "ooo"
    assert norm("You'll") == "youll"


def test_match_heard_pairs_accented_words():
    pairs = match_heard([W("Desceu", 1, 2), W("do", 2, 3), W("ônibus", 3, 4)],
                        [W("desceu", 1, 2), W("do", 2, 3), W("Ônibus,", 3, 4)])
    assert pairs == {0: 0, 1: 1, 2: 2}


def test_unsure_word_takes_the_heard_timing():
    aligned = [W("the", 69.0, 69.3), W("best", 73.68, 73.86, conf=0.0), W("is", 73.86, 73.98)]
    heard = [W("the", 69.0, 69.3), W("best", 69.38, 69.84, conf=0.9), W("is", 73.86, 73.98)]
    out = reconcile(aligned, heard, ends=set())
    assert (out[1].start, out[1].end, out[1].source) == (69.38, 69.84, "transcript")
    assert out[0] == aligned[0] and out[2] == aligned[2]


def test_word_stretched_back_over_a_break_takes_the_heard_start():
    aligned = [W("guest", 75.0, 76.0), W("Your", 77.10, 92.20, conf=0.44), W("uncle", 92.20, 92.60)]
    heard = [W("guest", 75.0, 76.0), W("Your", 91.21, 92.24), W("uncle", 92.25, 92.60)]
    out = reconcile(aligned, heard, ends={0})
    assert (out[1].start, out[1].end, out[1].source) == (91.21, 92.2, "transcript")


def test_confident_word_is_kept_when_the_transcription_disagrees():
    aligned = [W("home", 56.6, 57.0, conf=0.9)]
    assert reconcile(aligned, [W("home", 56.0, 56.3)], ends=set()) == aligned


def test_unsure_word_heard_too_far_away_is_kept_and_listed():
    aligned = [W("nine", 20.74, 22.5, conf=0.0), W("Coffee", 22.5, 22.62)]
    out = reconcile(aligned, [W("nine", 10.0, 10.4), W("Coffee", 22.05, 22.26)], ends={0})
    assert out[0] == aligned[0]
    assert suspects(out, {0}) == [0]


def test_word_on_silence_slides_to_the_next_voice_onset():
    out = snap_to_voice([W("The", 1.0, 1.5), W("last", 2.3, 2.8)], envelope([(2.0, 4.0)]))
    assert (out[0].start, out[0].end, out[0].source) == (2.0, 2.12, "snapped")
    assert out[1].source == "align"


def test_word_on_silence_with_no_onset_is_squeezed_before_the_next_word():
    out = snap_to_voice([W("A", 1.0, 1.2), W("little", 3.1, 3.5)], envelope([(3.1, 4.0)]))
    assert (out[0].start, out[0].end) == (2.98, 3.1)


def test_voiced_words_are_untouched_and_the_threshold_is_relative():
    words = [W("hey", 1.0, 1.5), W("you", 1.6, 2.0)]
    assert snap_to_voice(words, envelope([(0.0, 10.0)]) * 100) == words


def test_fix_moves_only_the_occurrence_nearest_the_given_time():
    words = [W("night", 53.1, 53.6), W("night", 115.0, 115.5), W("night", 176.0, 176.4)]
    out = apply_fixes(words, [{"at": "1:55", "word": "Night", "shift": 0.2}])
    assert (out[1].start, out[1].end, out[1].source) == (115.2, 115.7, "fixed")
    assert out[0] == words[0] and out[2] == words[2]


def test_fix_sets_explicit_times():
    out = apply_fixes([W("home", 56.6, 57.0)], [{"at": 56.6, "word": "home", "start": 56.4, "end": 57.2}])
    assert (out[0].start, out[0].end) == (56.4, 57.2)


def test_fix_errors_name_the_problem():
    words = [W("night", 53.1, 53.6)]
    with pytest.raises(MVError, match="no such word"):
        apply_fixes(words, [{"at": "0:10", "word": "night", "shift": 0.1}])
    with pytest.raises(MVError, match="too short"):
        apply_fixes(words, [{"at": 53, "word": "night", "start": 53.5, "end": 53.5}])
    with pytest.raises(MVError, match="needs"):
        apply_fixes(words, [{"word": "night"}])
    with pytest.raises(MVError, match="cannot read time"):
        apply_fixes(words, [{"at": "soon", "word": "night", "shift": 1}])


def test_show_changes_how_a_sung_word_is_written_everywhere_it_is_sung():
    lyrics = parse_lyrics("[Verse]\nNine-to-five again\nback to nine-to-five\n")
    words = [W("Nine-to-five", 1.0, 1.8), W("again", 1.8, 2.2), W("back", 5.0, 5.2), W("to", 5.2, 5.3),
             W("nine-to-five", 5.3, 6.0)]
    timing = show_words(build_timing(words, lyrics, 8.0), [{"word": "nine-to-five", "show": "9-to-5"}])
    assert [w["text"] for w in timing["words"]] == ["9-to-5", "again", "back", "to", "9-to-5"]
    assert [line["text"] for line in timing["lines"]] == ["9-to-5 again", "back to 9-to-5"]
    assert (timing["words"][0]["start"], timing["words"][0]["end"]) == (1.0, 1.8)


def test_show_with_at_changes_only_that_occurrence():
    lyrics = parse_lyrics("[Verse]\nfive and five\n")
    timing = build_timing([W("five", 1.0, 1.5), W("and", 1.5, 1.7), W("five", 30.0, 30.5)], lyrics, 40.0)
    out = show_words(timing, [{"at": "0:30", "word": "five", "show": "5"}])
    assert [w["text"] for w in out["words"]] == ["five", "and", "5"]
    assert out["lines"][0]["text"] == "five and 5"


def test_show_entries_are_not_timing_fixes_and_errors_name_the_word():
    words = [W("night", 53.1, 53.6)]
    assert apply_fixes(words, [{"word": "night", "show": "Night"}]) == words
    timing = build_timing(words, parse_lyrics("night"), 60.0)
    with pytest.raises(MVError, match="'day'"):
        show_words(timing, [{"word": "day", "show": "Day"}])
    assert show_words(timing, [{"at": 53.1, "word": "night", "shift": 0.1}]) == timing


def test_fixed_words_are_never_listed_as_unsure():
    assert suspects([W("x", 1.0, 1.1, conf=0.0, source="fixed")], set()) == []


def test_missing_lines_are_unsure_throughout_and_never_heard():
    lyrics = parse_lyrics("[Verse]\nhello there\nlost line\n")
    aligned = [W("hello", 1, 2), W("there", 2, 3), W("lost", 3, 4, conf=0.05), W("line", 4, 5, conf=0.1)]
    assert missing_lines(aligned, lyrics, heard_pairs={0: 0, 1: 1}) == [1]


def test_build_timing_shapes_words_lines_and_sections():
    lyrics = parse_lyrics("[Intro]\n[Verse 1]\nHello (hey)\n[Instrumental]\n[Chorus]\nSing it\n")
    words = [W("Hello", 1.0, 1.5), W("hey", 1.6, 1.9), W("Sing", 5.0, 5.4, source="snapped"), W("it", 5.4, 6.0)]
    timing = build_timing(words, lyrics, duration=8.0)
    assert timing["version"] == 1 and timing["duration"] == 8.0
    assert [w["text"] for w in timing["words"]] == ["Hello", "hey", "Sing", "it"]
    assert [w["backing"] for w in timing["words"]] == [False, True, False, False]
    assert timing["words"][2]["source"] == "snapped" and timing["words"][2]["line"] == 1
    assert timing["lines"][0] == {"i": 0, "text": "Hello (hey)", "section": 1, "backing": False,
                                  "start": 1.0, "end": 1.9, "words": [0, 1]}
    assert [(s["name"], s["start"], s["lines"]) for s in timing["sections"]] == [
        ("Intro", None, None), ("Verse 1", 1.0, [0, 0]), ("Instrumental", None, None), ("Chorus", 5.0, [1, 1])]


def test_build_timing_refuses_a_word_count_mismatch():
    with pytest.raises(MVError, match="2 timed words for 3 lyric words"):
        build_timing([W("a", 0, 1), W("b", 1, 2)], parse_lyrics("a b c"), 5.0)


def test_line_ends_and_clock():
    assert line_ends(parse_lyrics("a b\nc\nd e f\n")) == {1, 2, 5}
    assert clock(73.44) == "1:13.4"


def test_fix_with_a_non_numeric_value_names_the_fix():
    words = [W("night", 115.0, 115.5)]
    with pytest.raises(MVError, match="timing fix 'night' at 1:55: shift must be a number"):
        apply_fixes(words, [{"at": "1:55", "word": "night", "shift": "0,2"}])
