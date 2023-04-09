import os.path
import re
import subprocess
from shutil import which


def get_quality_preset(resolution_canon_name):
    if resolution_canon_name == '360p':
        return '-vf scale=-2:360'
    elif resolution_canon_name == '480p':
        return '-vf scale=-2:468'
    elif resolution_canon_name == '720p':
        return '-vf scale=-2:720'
    elif resolution_canon_name == '1080p':
        return '-vf scale=-2:1080'
    else:
        return ''


def get_video_frame_rate(filename):
    result = subprocess.run([
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        "-show_entries",
        "stream=r_frame_rate",
        filename,
    ], stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    result_string = result.stdout.decode('utf-8').split()[0].split('/')
    fps = float(result_string[0]) / float(result_string[1])
    return fps


def syscmd(cmd, encoding='utf8'):
    """
    Runs a command on the system, waits for the command to finish, and then
    returns the text output of the command. If the command produces no text
    output, the command's return code will be returned instead.
    """
    p = subprocess.Popen(cmd, shell=True, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                         close_fds=True)
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
        raise FileNotFoundError(f"File {path} does not exist")
    commnd = f"ffmpeg -v error -i {path} -c copy -f null -"
    # if the output is not empty then the file is invalid
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


def get_video_lenght(path):
    argv_ = f'ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "{path}"'
    result = syscmd(argv_)
    # if string
    if isinstance(result, str):
        # if contains N/A
        if 'N/A' in result:
            raise ValueError(f"File {path} is invalid, (encoded with aomenc?)")
    return float(result)


def get_total_bitrate(path) -> float:
    # get file size
    file_size = os.path.getsize(path)
    # get file length
    file_length = get_video_lenght(path)
    # get bitrate
    bitrate = file_size * 8 / file_length
    return bitrate


def get_video_vmeth(distorted_path, in_chunk=None, phone_model=False, disable_enchancment_gain=False, uhd_model=False):
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

    null_ = create_chunk_ffmpeg_pipe_command_using_chunk(in_chunk=in_chunk)
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


def get_video_ssim(distorted_path, in_chunk=None):
    null_ = create_chunk_ffmpeg_pipe_command_using_chunk(in_chunk=in_chunk)
    null_ += f" | ffmpeg -hide_banner -i - "

    null_ += f" -i {distorted_path} -filter_complex ssim -f null -"

    result_string = syscmd(null_, "utf8")
    try:
        match = re.search(r"All:\s*([\d.]+)", result_string)
        ssim_score = float(match.group(1))
        return ssim_score
    except AttributeError:
        print(f"Failed getting ssim comparing {distorted_path} agains {in_chunk.path}")
        print(null_)
        return 0


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
        # if the result does not contain a single number then it failed
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


def do_cropdetect(in_chunk=None):
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


def create_chunk_ffmpeg_pipe_command(resolution_canon_name="source", start_clip_time=0, end_clip_time=0, in_path="./no",
                                     framerate=-1):
    if framerate == -1:
        framerate = get_video_frame_rate(in_path)

    end_thingy = (float(end_clip_time) / framerate)
    start_time = (float(start_clip_time) / framerate)
    duration = (end_thingy - start_time)

    end_command = "ffmpeg -v error -nostdin "

    if start_clip_time != -1:
        end_command += f"-ss {str(start_time)} "

    end_command += f"-i {in_path} "

    if end_clip_time != -1:
        end_command += f"-t {str(duration)} "

    end_command += f"-an -sn -strict -1 {get_quality_preset(resolution_canon_name)} -f yuv4mpegpipe - "

    return end_command


def create_chunk_ffmpeg_pipe_command_using_chunk(resolution_canon_name="source", in_chunk=None):
    end_command = "ffmpeg -v error -nostdin "
    end_command += in_chunk.get_ss_ffmpeg_command_pair()
    end_command += f" -an -sn -strict -1 {get_quality_preset(resolution_canon_name)} -f yuv4mpegpipe - "

    return end_command


def get_width(in_path):
    if not os.path.exists(in_path):
        raise FileNotFoundError(f"File {in_path} does not exist")
    argv_ = f"ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 {in_path}"
    result = syscmd(argv_)
    return int(result)


def get_height(in_path):
    if not os.path.exists(in_path):
        raise FileNotFoundError(f"File {in_path} does not exist")
    argv_ = f"ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 {in_path}"
    result = syscmd(argv_)
    return int(result)


class EncoderConfigObject:
    """ A class to hold the configuration for the encoder """
    two_pass = True
    crop_string = ''
    bitrate = 0
    temp_folder = ''
    server_ip = ''
    remote_path = ''
    dry_run = False
    convexhull = False
    vmaf = 94
    grain_synth = -1


class EncoderJob:
    from hoeEncode.encode.ffmpeg.ChunkOffset import ChunkObject
    """ A class to hold the configuration for the encoder """

    def __init__(self, chunk: ChunkObject, current_scene_index: int, encoded_scene_path: str):
        self.chunk = chunk
        self.current_scene_index = current_scene_index
        self.encoded_scene_path = encoded_scene_path

    chunk: ChunkObject
    current_scene_index: int
    encoded_scene_path: str
