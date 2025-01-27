from math import ceil

from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.util.opinionated_vmaf import get_crf_limits
from alabamaEncode.core.util.timer import Timer
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.pipeline.chunk.chunk_analyse_step import (
    ChunkAnalyzePipelineItem,
)
from alabamaEncode.scene.chunk import ChunkObject


class LumaBoost(ChunkAnalyzePipelineItem):
    def run(self, ctx, chunk: ChunkObject, enc: Encoder) -> Encoder:
        luma_boost = ctx.get_kv().get("luma_boost", chunk.chunk_index)

        crf_min, crf_max = get_crf_limits(enc, ctx)

        if luma_boost is None:
            luma_boost = 0
            luma_boost_start_of_boosting_luma_score = (
                ctx.luma_boost_start_of_boosting_luma_score
            )
            luma_boost_end_of_boosting_luma_score = (
                ctx.luma_boost_end_of_boosting_luma_score
            )
            crf_boost_cap = ctx.luma_boost_cap

            timer = Timer()
            timer.start("luma_calc_time")
            clip_luma_score: float = Ffmpeg.get_chunk_brightness_score(chunk)  # 255-0
            luma_calc_time = timer.stop("luma_calc_time")

            if clip_luma_score <= luma_boost_start_of_boosting_luma_score:
                if clip_luma_score >= luma_boost_end_of_boosting_luma_score:
                    # linear interpolation
                    luma_boost = (
                        crf_boost_cap
                        * (luma_boost_start_of_boosting_luma_score - clip_luma_score)
                        / (
                            luma_boost_start_of_boosting_luma_score
                            - luma_boost_end_of_boosting_luma_score
                        )
                    )
                else:
                    luma_boost = crf_boost_cap

            if not enc.supports_float_crfs():
                luma_boost = ceil(luma_boost)

            ctx.log(
                f"{chunk.log_prefix()}calculated luma {clip_luma_score} in {luma_calc_time}s, boosted crf {luma_boost}",
                category="luma",
            )

            ctx.get_kv().set("luma_boost", chunk.chunk_index, luma_boost)

        enc.crf -= luma_boost
        enc.crf = max(min(enc.crf, crf_max), crf_min)

        return enc
