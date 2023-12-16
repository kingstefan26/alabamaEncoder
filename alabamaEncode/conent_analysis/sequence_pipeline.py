from typing import List, Callable

from alabamaEncode.conent_analysis.chunk_encode_pipeline import (
    setup_chunk_analyze_chain,
    setup_chunk_encoder,
)
from alabamaEncode.conent_analysis.sequence.autocrop import do_autocrop
from alabamaEncode.conent_analysis.sequence.denoise_filtering import setup_denoise
from alabamaEncode.conent_analysis.sequence.encoding_tiles import setup_tiles
from alabamaEncode.conent_analysis.sequence.ideal_crf import setup_ideal_crf_weighted
from alabamaEncode.conent_analysis.sequence.scrape_hdr_meta import scrape_hdr_metadata
from alabamaEncode.conent_analysis.sequence.sequence_autograin import setup_autograin
from alabamaEncode.conent_analysis.sequence.taget_ssimdb import setup_ssimdb_target
from alabamaEncode.conent_analysis.sequence.target_bitrate_optimisation import setup_ideal_bitrate


def get_pipeline() -> List[Callable]:
    pipeline = [
        setup_chunk_analyze_chain,
        setup_chunk_encoder,
        scrape_hdr_metadata,
        do_autocrop,
        setup_tiles,
        setup_denoise,
        setup_autograin,
        setup_ideal_crf_weighted,
        setup_ideal_bitrate,
        setup_ssimdb_target
    ]

    return pipeline


def run_sequence_pipeline(ctx, sequence):
    for func in get_pipeline():
        ctx = func(ctx, sequence)
    return ctx
