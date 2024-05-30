import os
import re

from alabamaEncode.core.util.cli_executor import run_cli
from alabamaEncode.core.util.bin_utils import get_binary


class ImageMetrics:
    @staticmethod
    def butteraugli_score(reference_img_path: str, distorted_img_path: str):
        if not os.path.exists(reference_img_path) or not os.path.exists(
            distorted_img_path
        ):
            raise FileNotFoundError("images not found, please check the paths")

        cli = f'{get_binary("butteraugli")} "{reference_img_path}"  "{distorted_img_path}"'
        try:
            result_string = run_cli(cli).get_output()
            # if the result does not contain a single number, then it failed
            if not re.search(r"[\d.]+", result_string):
                raise AttributeError

            return float(result_string)
        except AttributeError or ValueError:
            raise RuntimeError(f"Failed getting butteraugli, CLI: {cli}")

    @staticmethod
    def psnr_score(reference_img_path, distorted_img_path):
        cli = (
            f"{get_binary('ffmpeg')} -hide_banner -i {reference_img_path} -i {distorted_img_path} "
            f"-filter_complex psnr -f null -"
        )

        result_string = run_cli(cli).get_output()
        try:
            # Regex to get average score out of:
            # [Parsed_psnr_0 @ 0x55f6705fa200] PSNR y:49.460782 u:52.207017 v:51.497660 average:50.118351
            # min:48.908778 max:51.443411

            match = re.search(r"average:([\d.]+)", result_string)
            psnr_score = float(match.group(1))
            return psnr_score
        except AttributeError:
            print(
                f"Failed getting psnr comparing {reference_img_path} against {distorted_img_path}"
            )
            print(cli)
            return 0

    @staticmethod
    def ssim_score(reference_img_path, distorted_img_path):
        cli = f" ffmpeg -hide_banner -i {reference_img_path} -i {distorted_img_path} -filter_complex ssim -f null -"

        result_string = run_cli(cli).get_output()
        try:
            match = re.search(r"All:\s*([\d.]+)", result_string)
            ssim_score = float(match.group(1))
            return ssim_score
        except AttributeError:
            print(
                f"Failed getting ssim comparing {reference_img_path} against {distorted_img_path}"
            )
            print(cli)
            return 0

    @staticmethod
    def vmaf_score(reference_img_path, distorted_img_path):
        cli = f" ffmpeg -hide_banner -i {reference_img_path} -i {distorted_img_path} -lavfi libvmaf -f null -"

        result_string = run_cli(cli).get_output()
        try:
            match = re.compile(r"VMAF score: ([0-9]+\.[0-9]+)").search(result_string)
            vmaf_score = float(match.group(1))
            return vmaf_score
        except AttributeError:
            print(
                f"Failed getting vmath comparing {reference_img_path} against {distorted_img_path} command:"
            )
            print(cli)
            return 0
