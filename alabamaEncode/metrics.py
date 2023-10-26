import os
import re

from alabamaEncode.utils.binary import doesBinaryExist
from alabamaEncode.utils.execute import syscmd


class ImageMetrics:
    @staticmethod
    def butteraugli_score(refrence_img_path: str, distorted_img_path: str):
        if not os.path.exists(refrence_img_path) or not os.path.exists(
            distorted_img_path
        ):
            raise FileNotFoundError("images not found, please check the paths")

        binary = os.getenv("BUTTERAUGLI_PATH", "butteraugli")

        if not doesBinaryExist(binary):
            raise FileNotFoundError(
                f"butteraugli not found under {binary}, please check path/install it"
            )

        cli = f'{binary} "{refrence_img_path}"  "{distorted_img_path}"'
        try:
            result_string = syscmd(cli)
            # if the result does not contain a single number, then it failed
            if not re.search(r"[\d.]+", result_string):
                raise AttributeError

            return float(result_string)
        except AttributeError or ValueError:
            raise RuntimeError(f"Failed getting butteraugli, CLI: {cli}")

    @staticmethod
    def psnr_score(refrence_img_path, distorted_img_path):
        cli = f" ffmpeg -hide_banner -i {refrence_img_path} -i {distorted_img_path} -filter_complex psnr -f null -"

        result_string = syscmd(cli)
        try:
            # Regex to get avrage score out of:
            # [Parsed_psnr_0 @ 0x55f6705fa200] PSNR y:49.460782 u:52.207017 v:51.497660 average:50.118351
            # min:48.908778 max:51.443411

            match = re.search(r"average:([\d.]+)", result_string)
            psnr_score = float(match.group(1))
            return psnr_score
        except AttributeError:
            print(
                f"Failed getting psnr comparing {refrence_img_path} agains {distorted_img_path}"
            )
            print(cli)
            return 0

    @staticmethod
    def ssim_score(refrence_img_path, distorted_img_path):
        cli = f" ffmpeg -hide_banner -i {refrence_img_path} -i {distorted_img_path} -filter_complex ssim -f null -"

        result_string = syscmd(cli)
        try:
            match = re.search(r"All:\s*([\d.]+)", result_string)
            ssim_score = float(match.group(1))
            return ssim_score
        except AttributeError:
            print(
                f"Failed getting ssim comparing {refrence_img_path} agains {distorted_img_path}"
            )
            print(cli)
            return 0

    @staticmethod
    def vmaf_score(refrence_img_path, distorted_img_path):
        cli = f" ffmpeg -hide_banner -i {refrence_img_path} -i {distorted_img_path} -lavfi libvmaf -f null -"

        result_string = syscmd(cli)
        try:
            vmafRegex = re.compile(r"VMAF score: ([0-9]+\.[0-9]+)")
            match = vmafRegex.search(result_string)
            vmaf_score = float(match.group(1))
            return vmaf_score
        except AttributeError:
            print(
                f"Failed getting vmeth comparing {refrence_img_path} agains {distorted_img_path} command:"
            )
            print(cli)
            return 0
