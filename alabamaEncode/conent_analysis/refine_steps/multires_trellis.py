from alabamaEncode.conent_analysis.opinionated_vmaf import (
    get_vmaf_list,
    convexhull_get_crf_range,
    convexhull_get_resolutions,
)
from alabamaEncode.conent_analysis.refine_step import RefineStep
from alabamaEncode.encoder.codec import Codec


class MutliResTrellis(RefineStep):
    def __call__(self, ctx, sequence):
        if ctx.get_kv().get("multires_final_paths", "final_paths") is not None:
            print("Not calculating trellis, already done")
            return

        codec = ctx.prototype_encoder.get_codec()
        vmafs = get_vmaf_list(codec)
        crf_low, crf_high = convexhull_get_crf_range(codec)
        crf_range = list(range(crf_low, crf_high, 2))

        resolutions = convexhull_get_resolutions(codec)
        resolutions = [r.split(":")[0] for r in resolutions]

        # vmafs_values = []
        # for res in resolutions:
        #     for vmaf_target in vmafs:
        #         for chunk in sequence.chunks:
        #             for crf in crf_range:
        #                 data = ctx.get_kv().get(
        #                     "multi_res_candidates",
        #                     f"{chunk.chunk_index}_{res}_{crf}",
        #                 )
        #                 if data is not None:
        #                     vmafs_values.append(data["vmaf"])

        # scaled_max = max(vmafs_values)
        # pick based on percentiles
        # scaled_max = sorted(vmafs_values)[int(len(vmafs_values) * 0.85)]

        # max_target_vmaf = max(vmafs)
        # if scaled_max < max_target_vmaf:
        #     data_min = min(vmafs)
        #     range_unscaled = max_target_vmaf - min(vmafs)
        #     range_scales = scaled_max - data_min
        #     vmafs_scales = [(data - data_min) / range_unscaled for data in vmafs]
        #     print(vmafs_scales)
        #     vmafs = [data_min + (range_scales * data) for data in vmafs_scales]
        #
        #     print(
        #         f"Compressing vmaf range to: {data_min} - {scaled_max}; final vmaf targets: {vmafs}"
        #     )

        fps = sequence.chunks[0].framerate

        trellis_paths = {}
        for res in resolutions:
            for vmaf_target in vmafs:
                current_path = []
                print(f"Calculating trellis for res: {res} vmaf_target: {vmaf_target}")
                for chunk in sequence.chunks:
                    all_crfs = []
                    for crf in crf_range:
                        data = ctx.get_kv().get(
                            "multi_res_candidates",
                            f"{chunk.chunk_index}_{res}_{crf}",
                        )
                        if data is None:
                            continue
                        data = {
                            "vmaf": data["vmaf"],
                            "crf": data["crf"],
                            "bitrate": data["bitrate"],
                            "file": data["file"],
                            "res": data["res"],
                            "index": chunk.chunk_index,
                            "length": chunk.get_lenght(),
                        }
                        all_crfs.append(data)

                    # sort by vmaf error from the target vmaf

                    best_fit = all_crfs[0]
                    if ctx.prototype_encoder.get_codec() == Codec.av1:

                        def get_s(x):
                            frames = x["length"] * fps
                            bitrate = x["bitrate"]  # in kbps

                            # bitrate component
                            bitrate_weight = (bitrate / 650) ** 0.4 - 1
                            bitrate_weight *= 2

                            # Exponential component for the number of frames
                            size_kb = (frames * bitrate) / 1000
                            overall_size_weight = (size_kb / 250) ** 0.5
                            overall_size_weight = max(overall_size_weight, 1)

                            # Combine the components
                            combined_weight = bitrate_weight * overall_size_weight

                            # Ensure the combined weight is not negative
                            combined_weight = max(combined_weight, 0)
                            return abs(vmaf_target - x["vmaf"]) + combined_weight

                        all_crfs.sort(key=lambda x: get_s(x))
                        best_fit = all_crfs[0]

                    else:
                        all_crfs.sort(key=lambda x: abs(x["vmaf"] - vmaf_target))
                        best_fit = all_crfs[0]

                    current_path.append(best_fit)

                if f"{vmaf_target}" not in trellis_paths:
                    trellis_paths[f"{vmaf_target}"] = {}
                trellis_paths[f"{vmaf_target}"][f"{res}"] = current_path

        # now the filtering part, we need to pick the len(vmafs) best paths, one for each quality target
        vmafs_reverse = vmafs[::-1]
        prev_bitrate = -1
        final_paths = []
        for vmaf_target in vmafs_reverse:
            print("\n")
            trys_in_vmaf_group = trellis_paths[f"{vmaf_target}"]
            candidates = []
            for res in resolutions:
                paths_in_res = trys_in_vmaf_group[res]
                vmaf_errors = []
                bits = 0  # kb of all chunks together
                lengths = 0  # seconds of all chunks together
                for chunk in paths_in_res:
                    vmaf_errors.append(abs(chunk["vmaf"] - vmaf_target))
                    # get bits from bitrate and length filed
                    bits += chunk["bitrate"] * chunk["length"]
                    lengths += chunk["length"]

                vmaf_error_avg = sum(vmaf_errors) / len(vmaf_errors)
                bitrate = bits / lengths
                print(
                    f"vmaf target: {vmaf_target};   res: {res};   vmaf_error_avg: {vmaf_error_avg};  bitrate: {bitrate}"
                )
                candidates.append(
                    {
                        "vmaf_error_avg": vmaf_error_avg,
                        "bitrate": bitrate,
                        "res": res,
                        "paths": paths_in_res,
                    }
                )

            if prev_bitrate == -1:
                candidates.sort(key=lambda x: x["vmaf_error_avg"])
            else:
                candidates.sort(
                    key=lambda x: x["vmaf_error_avg"]
                    + min(abs(x["bitrate"] - prev_bitrate), 0)
                )

            best_candidate = candidates[0]
            print(
                f"best candidate for vmaf target {vmaf_target} is res: {best_candidate['res']} "
                f"with vmaf_error_avg: {best_candidate['vmaf_error_avg']}"
            )
            prev_bitrate = best_candidate["bitrate"]
            best_candidate = {
                **best_candidate,
                "vmaf_target": vmaf_target,
            }
            final_paths.append(best_candidate)

        # a = {
        #     "res": "720",
        #     "vmaf": "95",
        #     "chunks": [
        #         {"chunk_index": "0", "crf": "11"},
        #         {"chunk_index": "1", "crf": "12"},
        #     ],
        # }

        for path in final_paths:
            obj = {"res": path["res"], "chunks": []}

            for chunk in path["paths"]:
                obj["chunks"].append(
                    {
                        "chunk_index": chunk["index"],
                        "crf": chunk["crf"],
                    }
                )

            ctx.get_kv().set(
                "multires_trellis",
                f"{path['vmaf_target']}",
                obj,
            )

        ctx.get_kv().set("multires_final_paths", "final_paths", final_paths)
