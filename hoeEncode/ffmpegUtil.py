import os.path
import re
import subprocess
from shutil import which
from typing import List

from hoeEncode.sceneSplit.ChunkOffset import ChunkObject
from hoeEncode.sceneSplit.ChunkUtil import create_chunk_ffmpeg_pipe_command_using_chunk


def syscmd(cmd, encoding='utf8', timeout_value=-1):
    """
    Runs a command on the system, waits for the command to finish, and then
    returns the text output of the command. If the command produces no text
    output, the command's return code will be returned instead.
    """
    p = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         close_fds=True)
    if timeout_value > 0:
        p.wait(timeout=timeout_value)
    else:
        p.wait()
    output = p.stdout.read()
    if len(output) > 1:
        if encoding:
            return output.decode(encoding)
        else:
            return output
    return p.returncode


def check_for_invalid(path):
    if not os.path.exists(path):
        print(f"File {path} does not exist")
        return True
    commnd = f"ffmpeg -v error -i {path} -c copy -f null -"
    # if the output is not empty, then the file is invalid
    out = syscmd(commnd)
    # check if it's an int and if its 0
    if isinstance(out, int) and out == 0:
        return False
    else:
        return True


def get_frame_count(path):
    argv_ = f"ffprobe -v error -select_streams v:0 -count_packets -show_entries stream=nb_read_packets " \
            f'-of csv=p=0 "{path}"'
    result = syscmd(argv_)
    return int(result)


def get_video_lenght(path) -> float:
    """
    Returns the video length in seconds
    :param path: path to the video
    :return: float
    """
    result = syscmd(f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{path}"')
    if isinstance(result, str):
        if 'N/A' in result or 'Invalid data found' in result:
            raise ValueError(f"File {path} is invalid, (encoded with aomenc?)")
    return float(result)


def get_total_bitrate(path) -> float:
    return os.path.getsize(path) * 8 / get_video_lenght(path)


def get_video_vmeth(distorted_path, in_chunk=None, phone_model=False, disable_enchancment_gain=False, uhd_model=False,
                    crop_string=''):
    links = [
        ['https://github.com/Netflix/vmaf/raw/master/model/vmaf_4k_v0.6.1.json', 'vmaf_4k_v0.6.1.json'],
        ['https://github.com/Netflix/vmaf/raw/master/model/vmaf_v0.6.1.json', 'vmaf_v0.6.1.json'],
        ['https://github.com/Netflix/vmaf/raw/master/model/vmaf_4k_v0.6.1neg.json', 'vmaf_4k_v0.6.1neg.json'],
        ['https://github.com/Netflix/vmaf/raw/master/model/vmaf_v0.6.1neg.json', 'vmaf_v0.6.1neg.json']
    ]

    # 😍😍😍
    if phone_model is True or uhd_model is True:
        vmaf_models_dir = os.path.expanduser('~/vmaf_models')
        if not os.path.exists(vmaf_models_dir):
            os.makedirs(vmaf_models_dir)
        try:
            for link in links:
                if not os.path.exists(os.path.join(vmaf_models_dir, link[1])):
                    print("Downloading VMAF model")
                    syscmd(f"wget -O {vmaf_models_dir}/{link[1]} {link[0]}")

            for link in links:
                if not os.path.exists(os.path.join(vmaf_models_dir, link[1])):
                    raise FileNotFoundError(f"File {link[1]} does not exist")
            # 😍

        except Exception as e:
            print("Failed downloading VMAF models")
            print(e)
            return 0

    # turn the model paths into absolute paths
    vmaf_models_dir = os.path.expanduser('~/vmaf_models')
    for link in links:
        link[1] = os.path.join(vmaf_models_dir, link[1])

    null_ = create_chunk_ffmpeg_pipe_command_using_chunk(in_chunk=in_chunk, crop_string=crop_string)
    null_ += f" | ffmpeg -hide_banner -i - "

    lafi = "-lavfi libvmaf"
    if phone_model is True and disable_enchancment_gain is False:
        lafi = f"-lavfi libvmaf=model_path={links[1][1]}"
    elif phone_model is True and disable_enchancment_gain is True:
        lafi = f"-lavfi libvmaf=model_path={links[3][1]}"
    elif uhd_model is True and disable_enchancment_gain is False:
        lafi = f"-lavfi libvmaf=model_path={links[0][1]}"
    elif uhd_model is True and disable_enchancment_gain is True:
        lafi = f"-lavfi libvmaf=model_path={links[2][1]}"
    elif phone_model is False:
        lafi = "-lavfi libvmaf=phone_model=true"  # no documentation, just a guess

    null_ += f' -i {distorted_path} {lafi} -f null - '
    result_string = syscmd(null_, "utf8")
    try:
        vmafRegex = re.compile(r'VMAF score: ([0-9]+\.[0-9]+)')
        match = vmafRegex.search(result_string)
        vmaf_score = float(match.group(1))
        return vmaf_score
    except AttributeError:
        print(f"Failed getting vmeth comparing {distorted_path} agains {in_chunk.path} command:")
        print(null_)
        print(result_string)
        return 0


def get_video_ssim(distorted_path, in_chunk=None, print_output=False, get_db=False, crop_string=''):
    if not os.path.exists(in_chunk.path) or not os.path.exists(distorted_path):
        raise FileNotFoundError(f"File {in_chunk.path} or {distorted_path} does not exist")
    null_ = create_chunk_ffmpeg_pipe_command_using_chunk(in_chunk=in_chunk, crop_string=crop_string, bit_depth=10)

    null_ += f" | ffmpeg -hide_banner -i - -i {distorted_path} -filter_complex ssim -f null -"

    result_string = syscmd(null_, "utf8")
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


def get_source_bitrates(file_in: str, shutit=False) -> tuple[float, float]:
    """
    stolen from the one and only autocompressor.com's source code 🤑
    Returns tuple of bitrates (firstVideoStream, firstAudioStream)
    Works via demux-to-null (container stats are considered false)
    """
    common = '-show_entries packet=size -of default=nokey=1:noprint_wrappers=1'

    command_v = f'ffprobe -v error -select_streams V:0 {common} {file_in}'
    command_a = f'ffprobe -v error -select_streams a:0 {common} {file_in}'

    v_out = syscmd(command_v)
    if isinstance(v_out, int):
        print('Failed getting video bitrate')
        return 0, 0
    packets_v_arr = v_out.split('\n')

    a_out = syscmd(command_a)
    if isinstance(a_out, int):
        print('Failed getting video bitrate')
        return 0, 0
    packets_a_arr = a_out.split('\n')

    packets_v_bits = 0
    packets_a_bits = 0

    for i in packets_v_arr:
        if i.isdigit():
            packets_v_bits += int(i) * 8

    for j in packets_a_arr:
        if j.isdigit():
            packets_a_bits += int(j) * 8

    real_duration = get_video_lenght(file_in)

    vid_bps = round(packets_v_bits / real_duration)
    aud_bps = round(packets_a_bits / real_duration)
    if shutit is False:
        print(f'Video is {vid_bps} bps')
        print(f'Audio is {aud_bps} bps')

    return vid_bps, aud_bps


def get_video_psnr(distorted_path, in_chunk=None):
    null_ = create_chunk_ffmpeg_pipe_command_using_chunk(in_chunk=in_chunk)
    null_ += f" | ffmpeg -hide_banner -i - "

    null_ += f" -i {distorted_path} -filter_complex psnr -f null -"

    result_string = syscmd(null_, "utf8")
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
    null_ = f"butteraugli {refrence_img_path} {distorted_img_path}"
    try:
        result_string = syscmd(null_, "utf8")
        # if the result does not contain a single number, then it failed
        if not re.search(r"[\d.]+", result_string):
            raise AttributeError

        return float(result_string)
    except AttributeError:
        print(f"Failed getting butteraugli comparing {distorted_img_path} agains {refrence_img_path}")
        print(null_)
        return 0


def get_image_psnr_score(refrence_img_path, distorted_img_path):
    null_ = f" ffmpeg -hide_banner -i {refrence_img_path} -i {distorted_img_path} -filter_complex psnr -f null -"

    result_string = syscmd(null_, "utf8")
    try:
        # Regex to get avrage score out of:
        # [Parsed_psnr_0 @ 0x55f6705fa200] PSNR y:49.460782 u:52.207017 v:51.497660 average:50.118351
        # min:48.908778 max:51.443411

        match = re.search(r"average:([\d.]+)", result_string)
        psnr_score = float(match.group(1))
        return psnr_score
    except AttributeError:
        print(f"Failed getting psnr comparing {refrence_img_path} agains {distorted_img_path}")
        print(null_)
        return 0


def get_image_ssim_score(refrence_img_path, distorted_img_path):
    null_ = f" ffmpeg -hide_banner -i {refrence_img_path} -i {distorted_img_path} -filter_complex ssim -f null -"

    result_string = syscmd(null_, "utf8")
    try:
        match = re.search(r"All:\s*([\d.]+)", result_string)
        ssim_score = float(match.group(1))
        return ssim_score
    except AttributeError:
        print(f"Failed getting ssim comparing {refrence_img_path} agains {distorted_img_path}")
        print(null_)
        return 0


def get_image_vmaf_score(refrence_img_path, distorted_img_path):
    null_ = f" ffmpeg -hide_banner -i {refrence_img_path} -i {distorted_img_path} -lavfi libvmaf -f null -"

    result_string = syscmd(null_, "utf8")
    try:
        vmafRegex = re.compile(r'VMAF score: ([0-9]+\.[0-9]+)')
        match = vmafRegex.search(result_string)
        vmaf_score = float(match.group(1))
        return vmaf_score
    except AttributeError:
        print(f"Failed getting vmeth comparing {refrence_img_path} agains {distorted_img_path} command:")
        print(null_)
        return 0


def do_cropdetect(in_chunk: ChunkObject = None, path: str = None):
    sob = ''
    if in_chunk is None and path is None:
        raise ValueError("Either in_chunk or path must be set")
    if in_chunk is None and path is not None:
        lenght = get_frame_count(path)
        lenght = int(lenght / 2)
        in_chunk = ChunkObject(path=path, last_frame_index=lenght, first_frame_index=lenght - 100)

    sob = f'ffmpeg {in_chunk.get_ss_ffmpeg_command_pair()} -vframes 10 -vf cropdetect -f null -'

    result_string = syscmd(sob, "utf8")

    try:
        # [Parsed_cropdetect_0 @ 0x557cd612b6c0] x1:191 x2:1728 y1:0 y2:799 w:1536 h:800 x:192 y:0 pts:100498 t:4.187417 limit:0.094118 crop=1536:800:192:0
        # get the crop=number:number:number:number
        match = re.search(r'-?\d+:-?\d+:-?\d+:-?\d+', result_string)
        return match.group(0)
    except AttributeError:
        print(f"Failed auto-detecting crop from {in_chunk.path}")
        return ''


def doesBinaryExist(pathOrLocation):
    return which(pathOrLocation) is not None


def get_width(in_path):
    if not os.path.exists(in_path):
        raise FileNotFoundError(f"File {in_path} does not exist")
    argv_ = f'ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "{in_path}"'
    result = syscmd(argv_)
    return int(result)


def get_height(in_path):
    if not os.path.exists(in_path):
        raise FileNotFoundError(f"File {in_path} does not exist")
    argv_ = f'ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "{in_path}"'
    result = syscmd(argv_)
    return int(result)


def sizeof_fmt(num, suffix="B"):
    for unit in ["", "Ki", "Mi", "Gi", "Ti", "Pi", "Ei", "Zi"]:
        if abs(num) < 1024.0:
            return f"{num:3.1f}{unit}{suffix}"
        num /= 1024.0
    return f"{num:.1f}Yi{suffix}"
