import os
import shutil

from alabamaEncode.core.util.timer import Timer
from alabamaEncode.encoder.impl.X264 import EncoderX264
from alabamaEncode.encoder.rate_dist import EncoderRateDistribution
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.metrics.metric import Metric
from alabamaEncode.scene.chunk import ChunkObject
from alabamaEncode.scene.concat import VideoConcatenator
from alabamaEncode.scene.scene_detection import scene_detect

counter = 0

if __name__ == "__main__":
    env = "./experiments/CUCKS6"
    input_file = "/mnt/data/60seccut_1500offset.mkv"

    env = os.path.abspath(env)

    # if os.path.exists(env):
    #     shutil.rmtree(env)

    if not os.path.exists(env):
        os.makedirs(env)

    enc = EncoderX264()
    # enc.chunk = ChunkObject(
    #     path="/home/kokoniara/showsEncode/HALO (2022)/s1/e5/lossless.mkv"
    # )
    enc.chunk = ChunkObject(
        path="/mnt/data/objective-1-fast/Netflix_PierSeaside_1920x1080_60fps_8bit_420_60f.y4m"
    )
    # enc.grain_synth = 3
    enc.speed = 1
    enc.rate_distribution = EncoderRateDistribution.CQ
    # enc.crf = 20
    # enc.qm_enabled = 1
    # enc.qm_min = 0
    # enc.qm_max = 15
    # enc.threads = 12
    # enc.output_path = os.path.devnull

    # enc.matrix_coefficients = "bt2020-ncl"
    # enc.color_primaries = "bt2020"
    # enc.transfer_characteristics = "smpte2084"
    # enc.chroma_sample_position = "topleft"
    # enc.maximum_content_light_level = 358
    # enc.maximum_frame_average_light_level = 92
    # enc.svt_master_display = (
    #     "G(0.265,0.69)B(0.15,0.06)R(0.68,0.32)WP(0.3127,0.329)L(1000.0,0.005)"
    # )
    # enc.passes = 1
    # enc.hdr = True
    # enc.svt_cli_path = "/home/kokoniara/.local/opt/SvtAv1EncApp"

    # enc.video_filters = "atadenoise,hqdn3d=4,unsharp=7:7:0.5"
    enc.video_filters = "scale=1920:-2"

    # context = AlabamaContext()
    # context.vmaf = 95
    # context.log_level = 2
    # context.temp_folder = env
    # context.crf_model_weights = "0,0,0,0,1"

    # opt = TargetVmaf(alg_type="binary", probes=4, probe_speed=4)
    # enc = opt.run(context, enc.chunk, enc)
    #
    # print(enc.crf)
    # enc.output_path = os.path.join(env, "output.ivf")
    # print(enc.run(calculate_vmaf=True))

    # data = []

    scene_list = scene_detect(
        input_file=input_file,
        cache_file_path=env + "/sceneCache.pt",
        max_scene_length=10,
    )

    target_vmaf = 93
    epsilon_down = 0.3

    for chunk in scene_list.chunks:
        enc.chunk = chunk
        runs = []
        chunk_probes = os.path.join(env, f"{chunk.chunk_index}_probes")
        if not os.path.exists(chunk_probes):
            os.makedirs(chunk_probes)
        # for crf in range(10, 35):
        #     enc.crf = crf
        #     enc.output_path = os.path.join(env, f"{chunk_probes}/{crf}.mkv")
        #     stats: EncodeStats = enc.run(calculate_vmaf=True)
        #     stats.version = crf
        #     stats.basename = enc.output_path
        #     if stats.vmaf < target_vmaf - epsilon_down:
        #         break
        #     print(stats)
        #     cums.append(stats)

        # binary search version
        low_crf = 10
        high_crf = 35
        timer = Timer()
        timer.start("binary search")
        while low_crf <= high_crf:
            mid_crf = (low_crf + high_crf) // 2
            enc.crf = mid_crf
            enc.output_path = os.path.join(env, f"{chunk_probes}/{mid_crf}.mkv")
            timer.start(f"crf_{mid_crf}")
            stats: EncodeStats = enc.run(metric_to_calculate=Metric.VMAF)
            timer.stop(f"crf_{mid_crf}")
            stats.version = mid_crf
            stats.basename = enc.output_path
            runs.append(stats)
            print(stats)

            if abs(stats.vmaf - target_vmaf) <= epsilon_down:
                break
            elif stats.vmaf > target_vmaf:
                low_crf = mid_crf + 1
            else:
                high_crf = mid_crf - 1
        timer.stop("binary search")
        timer.finish(loud=True)

        closes_to_target = min(runs, key=lambda x: abs(x.vmaf - target_vmaf))
        # move closes to target to ../{index}.mkv
        shutil.move(
            closes_to_target.basename, os.path.join(env, f"{chunk.chunk_index}.mkv")
        )

    concat = VideoConcatenator(
        output=os.path.join(env, "output.mkv"), file_with_audio=input_file
    )
    concat.find_files_in_dir(
        folder_path=env,
        extension=".mkv",
    )
    concat.concat_videos()

    quit()

    # for crf in range(15, 40):
    #     enc.crf = crf
    #     enc.output_path = os.path.join(env, f"output_{crf}.mkv")
    #     stats: EncodeStats = enc.run(calculate_vmaf=True)
    #     stats.version = crf
    #     print(stats)
    #     dict_stats = stats.get_dict()
    #     data.append(dict_stats)
    #
    # json.dump(data, open(os.path.join(env, "data.json"), "w"))
