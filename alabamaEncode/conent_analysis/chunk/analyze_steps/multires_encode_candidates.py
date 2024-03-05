import os

from alabamaEncode.conent_analysis.chunk.chunk_analyse_step import (
    ChunkAnalyzePipelineItem,
)
from alabamaEncode.conent_analysis.opinionated_vmaf import (
    convexhull_get_resolutions,
    convexhull_get_crf_range,
)
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.metrics.calculate import get_metric_from_stats
from alabamaEncode.metrics.metric import Metric
from alabamaEncode.scene.chunk import ChunkObject


class EncodeMultiResCandidates(ChunkAnalyzePipelineItem):
    def run(self, ctx, chunk: ChunkObject, enc: Encoder) -> Encoder:
        crf_low, crf_high = convexhull_get_crf_range(enc.get_codec())
        crf_range = list(range(crf_low, crf_high, 2))
        resolutions = convexhull_get_resolutions(enc.get_codec())
        crf_range.reverse()  # encode the probes fast to slow, not necessary but why not
        resolutions.reverse()

        ctx.vmaf_reference_display = "FHD"
        vmaf_options = ctx.get_vmaf_options()

        probe_folder_path = (
            os.path.join(os.path.dirname(chunk.chunk_path), f"{chunk.chunk_index}")
            + os.path.sep
        )
        os.makedirs(probe_folder_path, exist_ok=True)

        ogspeed = enc.speed
        enc.speed = 13

        def log(_str):  # macro
            ctx.log(
                f"{chunk.log_prefix()}{_str}",
                category="multi_res",
            )

        for res in resolutions:
            vf = ctx.prototype_encoder.video_filters.split(",")
            scale_str = f"scale={res}:flags=lanczos"

            # replace the first scale filter if it exists
            for i in range(len(vf)):
                if ":flags=lanczos" in vf[i]:
                    vf[i] = scale_str
                    break

            # if there is no scale filter, add it to the end
            if scale_str not in ",".join(vf):
                vf.append(scale_str)

            vf = [f for f in vf if f != ""]

            enc.video_filters = ",".join(vf)

            for crf in crf_range:
                enc.crf = crf

                res_name_short = res.split(":")[0]

                enc.output_path = os.path.join(
                    probe_folder_path,
                    f"{chunk.chunk_index}.{res_name_short}.{crf}{enc.get_chunk_file_extension()}",
                )

                if ctx.get_kv().exists(
                    "multi_res_candidates",
                    f"{chunk.chunk_index}_{res_name_short}_{crf}",
                ):
                    continue

                stats: EncodeStats = enc.run(
                    metric_params=vmaf_options, metric_to_calculate=Metric.VMAF
                )

                vmaf = get_metric_from_stats(
                    stats, statistical_representation=ctx.vmaf_target_representation
                )

                log(f"Res: {res} VMAF: {vmaf} CRF: {crf} Bitrate: {stats.bitrate}")

                ctx.get_kv().set(
                    "multi_res_candidates",
                    f"{chunk.chunk_index}_{res_name_short}_{crf}",
                    {
                        "vmaf": vmaf,
                        "crf": crf,
                        "bitrate": stats.bitrate,
                        "file": enc.output_path,
                        "res": res,
                    },
                )

        enc.speed = ogspeed
        return enc
