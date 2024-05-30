import os

from matplotlib import pyplot as plt

from alabamaEncode.core.util.bin_utils import register_bin
from alabamaEncode.encoder.impl.X264 import EncoderX264
from alabamaEncode.metrics.comparison_display import ComparisonDisplayResolution
from alabamaEncode.scene.scene_detection import scene_detect
from alabamaEncode.scene.sequence import ChunkSequence

if __name__ == "__main__":
    env = "./convexhull"
    env = os.path.abspath(env)
    if not os.path.exists(env):
        os.mkdir(env)

    scenes: ChunkSequence = scene_detect(
        input_file="/home/kokoniara/ep3_halo_test.mkv",
        max_scene_length=10,
        cache_file_path=f"{env}/scenes_skinny.pt",
    )

    register_bin("SvtAv1EncApp", "/home/kokoniara/.local/opt/SvtAv1EncApp")
    target_vmaf = 90
    ref_dispaly = ComparisonDisplayResolution.FHD
    resoultions = [
        # "3840:-2",
        # "2560:-2",
        "1920:-2",
        "1366:-2",
        "1280:-2",
        "960:-2",
        "854:-2",
        "768:-2",
        "640:-2",
        "480:-2",
    ]

    crfs = range(15, 45, 2)
    pikle = os.path.join(env, "results_X264.pkl")
    import pickle

    results = []
    encs = [
        # EncoderSvtenc(),
        # EncoderVPX("vp9")
        EncoderX264()
    ]
    # for enc in encs:
    #     enc.chunk = scenes[4]
    #     enc.speed = 6
    #     if isinstance(enc, EncoderVPX):
    #         enc.speed = 4
    #     if isinstance(enc, EncoderX264):
    #         enc.speed = 2
    #     enc.passes = 1
    #     enc.threads = 12
    #
    #     for res in resoultions:
    #         for crf in crfs:
    #             filename = f"{res.split(':')[0]}p_{crf}_{enc.__class__.__name__}.{enc.get_chunk_file_extension()}"
    #             enc.output_path = os.path.join(env, filename)
    #             enc.video_filters = f"crop=3840:1920:0:120,scale={res}"
    #             enc.crf = crf
    #             stats = enc.run(
    #                 calculate_vmaf=True,
    #                 vmaf_params=VmafOptions(
    #                     ref=ref_dispaly,
    #                 ),
    #             )
    #             os.remove(enc.output_path)
    #             stats.basename = filename.replace(".ivf", "")
    #             stats.version = crf
    #             print(stats)
    #             results.append(stats)

    # with open(pikle, "wb") as f:
    #     pickle.dump(results, f)

    with open(pikle, "rb") as f:
        results = pickle.load(f)

    plt.figure(figsize=(10, 10))
    plt.title("convex hull of VMAF vs BITRATE")
    plt.xlabel("bitrate")
    # bitrate as log
    plt.xscale("log")
    plt.ylabel("VMAF")
    plt.grid(True)
    for enc in encs:
        # if not isinstance(enc, EncoderVPX):
        #     continue
        for res in resoultions:
            x = []
            y = []
            for stat in results:
                if (
                    stat.basename.startswith(f"{res.split(':')[0]}p")
                    and enc.__class__.__name__ in stat.basename
                ):
                    x.append(stat.bitrate)
                    y.append(stat.vmaf)

            plt.plot(x, y, label=f"{res} {enc.__class__.__name__}")

    plt.legend()
    plt.show()
    #
    # # speed vs vmaf
    # plt.figure(figsize=(10, 10))
    # plt.title("speed vs VMAF")
    # plt.xlabel("time_encoding")
    # plt.ylabel("VMAF")
    # plt.grid(True)
    # for enc in encs:
    #     # if not isinstance(enc, EncoderVPX):
    #     #     continue
    #     for res in resoultions:
    #         x = []
    #         y = []
    #         for stat in results:
    #             if stat.basename.startswith(
    #                 f"{res.split(':')[0]}p"
    #             ) and stat.basename.endswith(enc.__class__.__name__):
    #                 x.append(stat.time_encoding)
    #                 y.append(stat.vmaf)
    #
    #         plt.plot(x, y, label=f"{res} {enc.__class__.__name__}")
    #
    # plt.legend()
    # plt.savefig(os.path.join(env, "speed_vmaf.png"))
    # plt.show()

    vmaf_targets = [45, 55, 62, 68, 81, 87, 90, 93, 95, 97]
    for vmaf_target in vmaf_targets:
        # get res that will reach vmaf_target as close as possible, while having the lowest bitrate
        best_stat = None
        for enc in encs:
            # if not isinstance(enc, EncoderVPX):
            #     continue
            # for res in resoultions:
            #     x = []
            #     y = []
            #     z = []
            #     for stat in results:
            #         if (
            #             stat.basename.startswith(f"{res.split(':')[0]}p")
            #             and enc.__class__.__name__ in stat.basename
            #         ):
            #             x.append(stat.bitrate)
            #             y.append(stat.vmaf)
            #             z.append(stat.version)
            #
            #     for i in range(len(x)):
            #         if y[i] >= vmaf_target:
            #             if lowest_bitrate == 0 or x[i] < lowest_bitrate:
            #                 lowest_bitrate = x[i]
            #                 lowest_bitrate_res = res
            #                 closes_vmaf = y[i]
            #                 accompanying_crf = z[i]
            for stat in results:
                if enc.__class__.__name__ in stat.basename:
                    if best_stat is None:
                        best_stat = stat
                    score = abs(stat.vmaf - vmaf_target)
                    best_score = abs(best_stat.vmaf - vmaf_target)
                    if score < best_score:
                        best_stat = stat

        print(
            f"bitrate {best_stat.bitrate} @ {best_stat.version} crf {best_stat.basename.split('_')[0]} for vmaf {vmaf_target} "
            f"(got {best_stat.vmaf})"
        )
