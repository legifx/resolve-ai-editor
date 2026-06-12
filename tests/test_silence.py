from core.analyze.silence import Interval, invert_silences, parse_silencedetect

STDERR = """\
[silencedetect @ 0x1] silence_start: 2.0001
[silencedetect @ 0x1] silence_end: 3.5 | silence_duration: 1.4999
frame=  100 fps=0.0 ...
[silencedetect @ 0x1] silence_start: 5.0
"""


def test_parse_pairs_and_trailing_eof():
    out = parse_silencedetect(STDERR, total_duration=6.0)
    assert len(out) == 2
    assert abs(out[0].start - 2.0001) < 1e-6 and out[0].end == 3.5
    # trailing silence_start without end runs to EOF
    assert out[1] == Interval(5.0, 6.0)


def test_parse_clamps_negative_start_and_overlong_end():
    text = ("silence_start: -0.4\n"
            "silence_end: 99.0 | silence_duration: 99.4\n")
    out = parse_silencedetect(text, total_duration=10.0)
    assert out == [Interval(0.0, 10.0)]


def test_parse_ignores_end_without_start():
    assert parse_silencedetect("silence_end: 3.0 | x\n", 10.0) == []


def test_invert_basic():
    keeps = invert_silences([Interval(2.0, 3.5), Interval(5.0, 6.0)], 6.0)
    assert keeps == [Interval(0.0, 2.0), Interval(3.5, 5.0)]


def test_invert_no_silence_keeps_everything():
    assert invert_silences([], 4.0) == [Interval(0.0, 4.0)]


def test_invert_drops_micro_slivers():
    # 0.1 s of 'speech' between two silences is below min_keep=0.15
    sil = [Interval(0.0, 2.0), Interval(2.1, 4.0)]
    assert invert_silences(sil, 4.0) == []


def test_invert_unsorted_input():
    sil = [Interval(5.0, 6.0), Interval(2.0, 3.5)]
    keeps = invert_silences(sil, 6.0)
    assert keeps == [Interval(0.0, 2.0), Interval(3.5, 5.0)]
