import os.path
import re
from typing import Any, Dict

from alabamaEncode.cli_executor import run_cli
from alabamaEncode.ffmpeg import Ffmpeg
from alabamaEncode.metrics import ImageMetrics
from alabamaEncode.path import PathAlabama
from alabamaEncode.scene.chunk import ChunkObject


def get_video_vmeth(
    distorted_path,
    in_chunk: ChunkObject = None,
    video_filters="",
    phone_model=False,
    disable_enchancment_gain=False,
    uhd_model=False,
    log_path="",
    threads=1,
    vmaf_options: Dict[str, Any] = None,
):
    """
    Returns the VMAF score of the video
    :param threads:
    :param log_path:
    :param distorted_path: path to the distorted video
    :param in_chunk: ChunkObject
    :param phone_model:
    :param disable_enchancment_gain:
    :param uhd_model:
    :param video_filters:
    :return:
    """
    links = [
        [
            "https://github.com/Netflix/vmaf/raw/master/model/vmaf_4k_v0.6.1.json",
            "vmaf_4k_v0.6.1.json",
        ],
        [
            "https://github.com/Netflix/vmaf/raw/master/model/vmaf_v0.6.1.json",
            "vmaf_v0.6.1.json",
        ],
        [
            "https://github.com/Netflix/vmaf/raw/master/model/vmaf_4k_v0.6.1neg.json",
            "vmaf_4k_v0.6.1neg.json",
        ],
        [
            "https://github.com/Netflix/vmaf/raw/master/model/vmaf_v0.6.1neg.json",
            "vmaf_v0.6.1neg.json",
        ],
    ]

    # 😍😍😍
    if phone_model is True or uhd_model is True:
        vmaf_models_dir = os.path.expanduser("~/vmaf_models")
        if not os.path.exists(vmaf_models_dir):
            os.makedirs(vmaf_models_dir)
        try:
            for link in links:
                if not os.path.exists(os.path.join(vmaf_models_dir, link[1])):
                    print("Downloading VMAF model")
                    run_cli(f"wget -O {vmaf_models_dir}/{link[1]} {link[0]}")

            for link in links:
                if not os.path.exists(os.path.join(vmaf_models_dir, link[1])):
                    raise FileNotFoundError(f"File {link[1]} does not exist")
            # 😍

        except Exception as e:
            print("Failed downloading VMAF models")
            print(e)
            return 0

    # turn the model paths into absolute paths
    vmaf_models_dir = os.path.expanduser("~/vmaf_models")
    for link in links:
        link[1] = os.path.join(vmaf_models_dir, link[1])

    # ffmpeg -hide_banner -i tst.mp4 -i tst_av1.webm -lavfi libvmaf='model=path=model.json:feature=name=psnr|name=ciede|name=cambi|name=psnr_hvs:log_path=out.json:log_fmt=xml:threads=12' -f null -

    if (Ffmpeg.get_tonemap_vf() in video_filters) is False and Ffmpeg.is_hdr(
        PathAlabama(in_chunk.path)
    ):
        if video_filters != "":
            video_filters += ","
        video_filters += Ffmpeg.get_tonemap_vf()

    null_ = in_chunk.create_chunk_ffmpeg_pipe_command(video_filters=video_filters)
    null_ += f" | ffmpeg -hide_banner -i - "

    option_arr = []

    model_path = ""

    if phone_model is True and disable_enchancment_gain is False:
        model_path = links[1][1]
    elif phone_model is True and disable_enchancment_gain is True:
        model_path = links[3][1]
    elif uhd_model is True and disable_enchancment_gain is False:
        model_path = links[0][1]
    elif uhd_model is True and disable_enchancment_gain is True:
        model_path = links[2][1]

    if model_path != "":
        option_arr += [f"model=path={model_path}"]

    if log_path:
        option_arr += [f"log_path={log_path}"]
        option_arr += [f"log_fmt=json"]

    if threads > 1:
        option_arr += [f"threads={threads}"]

    if vmaf_options is not None:
        features = vmaf_options.get("features", [])
        ftr = []
        for feature in features:
            ftr += [f"name={feature}"]

        if len(ftr) > 0:
            option_arr += [f"feature={'|'.join(ftr)}"]

    option_str = ":".join(option_arr)

    if Ffmpeg.is_hdr(PathAlabama(distorted_path)):
        null_ += f'-i "{distorted_path}" -lavfi "[1:v]{Ffmpeg.get_tonemap_vf()}[distorted];[0:v][distorted]libvmaf=\'{option_str}\'" -f null - '
    else:
        null_ += f'-i "{distorted_path}" -lavfi libvmaf="{option_str}" -f null - '

    result_string = run_cli(null_).get_output()
    try:
        vmafRegex = re.compile(r"VMAF score: ([0-9]+\.[0-9]+)")
        match = vmafRegex.search(result_string)
        vmaf_score = float(match.group(1))
        return vmaf_score
    except AttributeError:
        print(
            f"Failed getting vmeth comparing {distorted_path} agains {in_chunk.path} command:"
        )
        print(null_)
        print(result_string)
        return 0


def get_video_ssim(
    distorted_path,
    in_chunk: ChunkObject = None,
    print_output=False,
    get_db=False,
    video_filters="",
):
    if not os.path.exists(in_chunk.path) or not os.path.exists(distorted_path):
        raise FileNotFoundError(
            f"File {in_chunk.path} or {distorted_path} does not exist"
        )
    null_ = in_chunk.create_chunk_ffmpeg_pipe_command(video_filters=video_filters)

    null_ += f" | ffmpeg -hide_banner -i - -i {distorted_path} -filter_complex ssim -f null -"

    result_string = run_cli(null_).get_output()
    if print_output:
        print(result_string)
    try:
        if get_db is True:
            # Regex to get avrage score out of:
            # [Parsed_ssim_0 @ 0x55f6705fa200] SSIM Y:0.999999 (0.000000 dB) U:0.999999 (0.000000 dB) V:0.999999 (0.000000 dB) All:0.999999 (0.000000)
            match = re.search(r"All:([\d.]+) \(([\d.]+)", result_string)
            ssim_score = float(match.group(1))
            ssim_db = float(match.group(2))
            return ssim_score, ssim_db
        else:
            match = re.search(r"All:\s*([\d.]+)", result_string)
            ssim_score = float(match.group(1))
            return ssim_score
    except AttributeError:
        print(f"Failed getting ssim comparing {distorted_path} agains {in_chunk.path}")
        print(null_)
        return 0


def get_video_psnr(distorted_path, in_chunk: ChunkObject = None):
    null_ = in_chunk.create_chunk_ffmpeg_pipe_command()
    null_ += f" | ffmpeg -hide_banner -i - "

    null_ += f" -i {distorted_path} -filter_complex psnr -f null -"

    result_string = run_cli(null_).get_output()
    try:
        # Regex to get avrage score out of:
        # [Parsed_psnr_0 @ 0x55f6705fa200] PSNR y:49.460782 u:52.207017 v:51.497660 average:50.118351
        # min:48.908778 max:51.443411

        match = re.search(r"average:([\d.]+)", result_string)
        psnr_score = float(match.group(1))
        return psnr_score
    except AttributeError:
        print(f"Failed getting psnr comparing {distorted_path} agains {in_chunk.path}")
        print(null_)
        return 0


def get_image_butteraugli_score(refrence_img_path, distorted_img_path):
    return ImageMetrics.butteraugli_score(refrence_img_path, distorted_img_path)

    # null_ = f'butteraugli "{refrence_img_path}"  "{distorted_img_path}"'
    # try:
    #     result_string = syscmd(null_, "utf8")
    #     # if the result does not contain a single number, then it failed
    #     if not re.search(r"[\d.]+", result_string):
    #         raise AttributeError
    #
    #     return float(result_string)
    # except AttributeError or ValueError:
    #     print("CLI: " + null_)
    #     print(
    #         f"Failed getting butteraugli comparing {distorted_img_path} agains {refrence_img_path}"
    #     )
    #     print(null_)
    #     return 0


def do_cropdetect(in_chunk: ChunkObject = None, path: str = None):
    if in_chunk is None and path is None:
        raise ValueError("Either in_chunk or path must be set")
    if in_chunk is None and path is not None:
        lenght = Ffmpeg.get_frame_count(PathAlabama(path))
        lenght = int(lenght / 2)
        in_chunk = ChunkObject(
            path=path, last_frame_index=lenght, first_frame_index=lenght - 100
        )
    print("Starting cropdetect")
    sob = f"ffmpeg {in_chunk.get_ss_ffmpeg_command_pair()} -vframes 10 -vf cropdetect -f null -"

    result_string = run_cli(sob).get_output()
    try:
        # [Parsed_cropdetect_0 @ 0x557cd612b6c0] x1:191 x2:1728 y1:0 y2:799 w:1536 h:800 x:192 y:0 pts:100498 t:4.187417 limit:0.094118 crop=1536:800:192:0
        # get the crop=number:number:number:number
        match = re.search(r"-?\d+:-?\d+:-?\d+:-?\d+", result_string)
        print(f"Finished cropdetect, parsed {match.group(0)}")
        return match.group(0)
    except AttributeError:
        print(f"Failed auto-detecting crop from {in_chunk.path}")
        return ""
