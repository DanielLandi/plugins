from musicvideo.video.subtitles import lrc_time, srt_time, to_lrc, to_srt, to_vtt, vtt_time


def word(i, text, start, end, line):
    return {"i": i, "text": text, "start": start, "end": end, "conf": 0.9, "source": "align",
            "line": line, "backing": False}


TIMING = {
    "version": 1, "duration": 5.0,
    "words": [word(0, "Ônibus", 1.0, 1.4, 0), word(1, "no", 1.5, 1.7, 0), word(2, "morro", 1.8, 2.6, 0),
              word(3, "Rock", 2.4, 3.0, 1), word(4, "&", 3.0, 3.1, 1), word(5, "roll", 3.2, 3.9, 1)],
    "lines": [{"i": 0, "text": "Ônibus no morro", "section": 0, "backing": False, "start": 1.0, "end": 2.6,
               "words": [0, 2]},
              {"i": 1, "text": "Rock & roll", "section": 0, "backing": False, "start": 2.4, "end": 3.9,
               "words": [3, 5]}],
    "sections": [{"i": 0, "name": "Verse", "start": 1.0, "end": 3.9, "lines": [0, 1]}],
}


def test_clock_formats():
    assert lrc_time(65.456) == "01:05.46"
    assert srt_time(3725.5) == "01:02:05,500"
    assert vtt_time(0.04) == "00:00:00.040"


def test_lrc_has_line_and_word_times_and_keeps_accents():
    lrc = to_lrc(TIMING, "Estrada", "Banda")
    assert lrc.splitlines() == [
        "[ti:Estrada]", "[ar:Banda]",
        "[00:01.00]<00:01.00>Ônibus <00:01.50>no <00:01.80>morro",
        "[00:02.40]<00:02.40>Rock <00:03.00>& <00:03.20>roll",
    ]


def test_srt_ends_a_line_where_the_next_begins():
    assert to_srt(TIMING) == ("1\n00:00:01,000 --> 00:00:02,400\nÔnibus no morro\n\n"
                              "2\n00:00:02,400 --> 00:00:03,900\nRock & roll\n")


def test_vtt_tags_words_after_the_first_and_escapes_markup():
    vtt = to_vtt(TIMING)
    assert vtt.startswith("WEBVTT\n\n")
    assert "00:00:01.000 --> 00:00:02.400\nÔnibus <00:00:01.500>no <00:00:01.800>morro\n" in vtt
    assert "00:00:02.400 --> 00:00:03.900\nRock <00:00:03.000>&amp; <00:00:03.200>roll\n" in vtt
