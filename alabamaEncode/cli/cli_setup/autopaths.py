import os
import re

from alabamaEncode.core.context import AlabamaContext


def parse_movie_title(title):
    match = re.match(r"^(.*?) \((\d{4})\)$", title)
    if match:
        return match.group(1), match.group(2)
    return None


def parse_tv_title(title):
    """
    Parses a tv title and returns the title, year, season and episode
    """
    match = re.match(r"^(.*?) \((\d{4})\) S(\d{2})E(\d{2})$", title)
    if match:
        return match.group(1), match.group(2), match.group(3), match.group(4)
    return None


def is_title_movie(title):
    """
    Returns true if the title is a movie
    """
    return title[-1] == ")"


def is_valid_title(title):
    """
    Returns true if the title is a movie or tv show
    """
    return is_title_movie(title) or re.match(
        r"^(.*?) \((\d{4})\) S(\d{2})E(\d{2})$", title
    )


def auto_output_paths(ctx):
    """
    If output file is set to "auto" compute the output file name from title
    """
    if ctx.output_file == "auto":
        if ctx.title == "":
            print(
                '`--title "Title (year) [S--E--|Nothing for movies]"` must be set if output file is set to auto'
            )
            quit()
        if not is_valid_title(ctx.title):
            print(
                f"Title {ctx.title} is not valid, must be in the format `Title (year) [SExx|Nothing for movies]`"
            )
            quit()

        is_movie = is_title_movie(title=ctx.title)
        # ~/showsEncode/Title/sx/ex/Title.YEAR.S0xE0x.{ctx.encoder_name}.webm
        # ~/movieEncode/Title/Title.YEAR.{ctx.encoder_name}.webm

        hdr_bit = ".HDR10" if ctx.prototype_encoder.hdr else ""
        res_preset = "." + ctx.resolution_preset if ctx.resolution_preset != "" else ""

        if is_movie:
            title, year = parse_movie_title(ctx.title)
            ctx.output_file = (
                f"~/movieEncode/{title} ({year})/"
                f"{title.replace(' ', '.')}.{year}{res_preset}.AV1.OPUS{hdr_bit}.{ctx.encoder_name}.webm"
            )
        else:
            title, year, season, episode = parse_tv_title(ctx.title)
            ctx.output_file = (
                f"~/showsEncode/{title} ({year})/s{int(season)}/e{int(episode)}/"
                f"{title.replace(' ', '.')}.{year}.S{season}E{episode}{res_preset}"
                f".AV1.OPUS{hdr_bit}.{ctx.encoder_name}.webm"
            )

        ctx.output_file = os.path.expanduser(ctx.output_file)

    return ctx


def movie_parser_test():
    title = "The Matrix (1999)"
    title, year = parse_movie_title(title)
    assert title == "The Matrix"
    assert year == "1999"

    title = "Movie (2020)"
    title, year = parse_movie_title(title)
    assert title == "Movie"
    assert year == "2020"


def tv_parser_test():
    title = "The Matrix (1999) S01E01"
    title, year, season, episode = parse_tv_title(title)
    assert title == "The Matrix"
    assert year == "1999"
    assert season == "01"
    assert episode == "01"


def title_validator_test():
    title = "The Matrix (1999)"
    assert is_valid_title(title)

    title = "The Matrix (1999) S01E01"
    assert is_valid_title(title)

    title = "The matrix 1999 S01E01"
    assert not is_valid_title(title)

    title = "The Matrix S01E01"
    assert not is_valid_title(title)

    title = "The Matrix () S01E01"
    assert not is_valid_title(title)


def test_auto_paths():
    ctx = AlabamaContext()
    ctx.encoder_name = "SouAV1R"
    home = os.path.expanduser("~")

    ctx.output_file = "auto"
    ctx.title = "The Matrix (1999)"
    ctx = auto_output_paths(ctx)
    print(ctx.output_file)
    assert (
        ctx.output_file
        == f"{home}/movieEncode/The Matrix (1999)/The.Matrix.1999.AV1.OPUS.SouAV1R.webm"
    )

    ctx.output_file = "auto"
    ctx.title = "The Matrix (1999) S01E01"
    ctx = auto_output_paths(ctx)

    print(ctx.output_file)
    assert (
        ctx.output_file
        == f"{home}/showsEncode/The Matrix (1999)/s1/e1/The.Matrix.1999.S01E01.AV1.OPUS.SouAV1R.webm"
    )


if __name__ == "__main__":
    movie_parser_test()
    tv_parser_test()
    title_validator_test()
    test_auto_paths()
