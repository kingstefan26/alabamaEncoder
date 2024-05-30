import os

from alabamaEncode.conent_analysis.chunk.final_encode_step import (
    FinalEncodeStep,
)
from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.metrics.calculate import get_metric_from_stats
from alabamaEncode.metrics.metric import Metric
from alabamaEncode.scene.chunk import ChunkObject


class DynamicTargetVmafVBR(FinalEncodeStep):
    def run(
        self, enc: Encoder, chunk: ChunkObject, ctx: AlabamaContext, encoded_a_frame
    ) -> EncodeStats:
        vmaf_options = ctx.get_vmaf_options()
        probe_file_base = ctx.get_probe_file_base(chunk.chunk_path)
        enc.passes = 3
        enc.rate_distribution = EncoderRateDistribution.VBR
        metric_name = "vmaf"
        original_output_path = enc.output_path
        low_bitrate = 250
        low_bitrate_cap = 250
        high_bitrate = 5000
        high_bitrate_cap = 20_000
        target_vmaf = ctx.vmaf
        trys = []
        max_vmaf_error = 0.5
        stats = None
        binary_search_steps = 4
        interpol_steps = 3
        mid_bitrate = 2000

        total_encodes = 0

        def log(_str):
            ctx.log(
                f"{chunk.log_prefix()}{_str}",
                category="probe",
            )

        def get_score(_bitrate):
            enc.bitrate = _bitrate
            enc.output_path = os.path.join(
                probe_file_base,
                f"{chunk.chunk_index}.{_bitrate}{enc.get_chunk_file_extension()}",
            )
            stats: EncodeStats = enc.run(
                metric_to_calculate=Metric.VMAF,
                metric_params=vmaf_options,
                override_if_exists=False,
            )
            nonlocal total_encodes
            total_encodes += 1
            metric = get_metric_from_stats(
                stats, statistical_representation=ctx.vmaf_target_representation
            )
            metric_error = abs(metric - target_vmaf)
            log(
                f"bitrate: {stats.bitrate}; {metric_name}: {metric}; error: {metric_error}"
                f" attempt {total_encodes}/{binary_search_steps + interpol_steps}"
            )
            nonlocal trys
            trys.append((_bitrate, metric))
            return metric, enc.output_path, stats

        def finish(_stats, bitrate, additional_message=""):
            prefi = f"{additional_message}; " if additional_message != "" else ""
            log(
                f"{prefi}bitrate {bitrate}; {metric_name}: {get_metric_from_stats(_stats, ctx.vmaf_target_representation)};"
                f" real bitrate: {_stats.bitrate} kb/s"
            )
            ctx.get_kv().set("best_bitrates", chunk.chunk_index, bitrate)
            os.rename(enc.output_path, original_output_path)
            return _stats

        for search_step in range(binary_search_steps):
            if search_step > 0:
                mid_bitrate = (low_bitrate + high_bitrate) // 2
            elif search_step == 0:
                if len(ctx.best_crfs) > 2:
                    # set the mean of the best crf's so far as the first guess
                    best_bitrates = ctx.get_kv().get_all("best_bitrates")
                    mid_bitrate = int(sum(best_bitrates.values()) / len(best_bitrates))

                    log(f"overriding first attempt to {mid_bitrate}")

            mid_vmaf, probe_path, stats = get_score(mid_bitrate)

            current_metric_error = abs(target_vmaf - mid_vmaf)
            if current_metric_error < max_vmaf_error:
                return finish(
                    stats,
                    mid_bitrate,
                    additional_message=f"Probe within error ({current_metric_error})",
                )

            # check if two probes had the same vmaf, if so quit early since its prob a black screen
            if len(trys) > 1 and trys[-1][1] == trys[-2][1]:
                return finish(
                    stats,
                    mid_bitrate,
                    additional_message=f"Two probes same {metric_name} quiting",
                )

            if mid_vmaf < target_vmaf:
                low_bitrate = mid_bitrate
            else:
                high_bitrate = mid_bitrate

        for interpol_step in range(interpol_steps):
            # sort by vmaf difference from target
            points = sorted(trys, key=lambda _x: abs(_x[1] - target_vmaf))

            # get the two closest points
            bitrate_low, metric_low = points[0]
            bitrate_high, metric_high = points[1]

            # if the difference bettwen metric_low and metric_high is less than metric_high and metric_high,
            # then use the high point instead of the low point
            if len(points) > 2:
                if abs(metric_low - metric_high) < abs(metric_high - points[2][1]):
                    bitrate_high, metric_high = points[2]

            interpolated_bitrate = bitrate_low + (bitrate_high - bitrate_low) * (
                (target_vmaf - metric_low) / (metric_high - metric_low)
            )

            interpolated_bitrate = max(
                min(interpolated_bitrate, high_bitrate_cap), low_bitrate_cap
            )

            interpolated_bitrate = round(interpolated_bitrate)

            # quit early if interpolated bitrate is in trys
            if any([abs(_x[0] - interpolated_bitrate) < 25 for _x in trys]):
                return finish(
                    stats,
                    interpolated_bitrate,
                    additional_message=f"intrpol bitrate {interpolated_bitrate} already tried",
                )

            log(f"Interpolate pass {interpol_step}: bitrate {interpolated_bitrate}")
            metric, probe_path, stats = get_score(interpolated_bitrate)
            current_metric_error = abs(target_vmaf - metric)
            if current_metric_error <= max_vmaf_error:
                return finish(
                    stats,
                    interpolated_bitrate,
                    additional_message=f"Probe within error ({current_metric_error})",
                )

        return finish(
            stats, interpolated_bitrate, additional_message="Failed to hit target"
        )

    def dry_run(self, enc: Encoder, chunk: ChunkObject) -> str:
        raise Exception(f"dry_run not implemented for {self.__class__.__name__}")
