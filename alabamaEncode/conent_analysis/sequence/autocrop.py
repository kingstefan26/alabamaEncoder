import os
import re
import time
from typing import List

from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.util.bin_utils import get_binary
from alabamaEncode.core.util.cli_executor import run_cli
from alabamaEncode.core.util.path import PathAlabama
from alabamaEncode.scene.chunk import ChunkObject
from alabamaEncode.scene.sequence import ChunkSequence


def do_autocrop(ctx: AlabamaContext, sequence: ChunkSequence):
    """
    Does autocrop if needed
    """
    if ctx.auto_crop and ctx.crop_string == "":
        output = ctx.get_kv().get_global("autocrop")
        if output is None:
            start = time.time()
            print("Running cropdetect...")
            output = do_cropdetect(ctx.input_file)
            print(f"Computed crop: {output} in {int(time.time() - start)}s")
            path = PathAlabama(ctx.input_file)
            out_path = PathAlabama(ctx.output_file)

            def gen_prew(ss, i) -> List[str]:
                _p = f'"{out_path.get()}.{i}.cropped.jpg"'
                run_cli(
                    f"{get_binary('ffmpeg')} -v error -y -ss {ss} -i {path.get_safe()} "
                    f"-vf crop={output} -vframes 1 {_p}"
                ).verify()
                p2 = f'"{out_path.get()}.{i}.uncropped.jpg"'
                run_cli(
                    f"{get_binary('ffmpeg')} -v error -y -ss {ss} -i {path.get_safe()} -vframes 1 {p2}"
                )
                return [_p.replace('"', ""), p2.replace('"', "")]

            if not ctx.auto_accept_autocrop:
                print("Creating previews")
                generated_paths = gen_prew(60, 0)
                generated_paths += gen_prew(120, 1)
                print(
                    "Created crop previews in output folder, if you want to use this crop,"
                    " click enter, type anything to abort"
                )

                if input() != "":
                    print("Aborting")
                    for p in generated_paths:
                        if os.path.exists(p):
                            os.remove(p)
                    quit()

                for p in generated_paths:
                    if os.path.exists(p):
                        os.remove(p)

            ctx.get_kv().set_global("autocrop", output)

        vf = ctx.prototype_encoder.video_filters.split(",")
        for i in range(len(vf)):
            if "crop=" in vf[i]:
                vf[i] = f"crop={output}"
        if "crop=" not in ",".join(vf):
            # add to the start
            vf.insert(0, f"crop={output}")

        ctx.prototype_encoder.video_filters = ",".join(vf)

    return ctx


if __name__ == "__main__":
    print("AUTOCROP IMPLEMENTATION TEST")
    ctx = AlabamaContext()
    ctx.auto_crop = True
    ctx.input_file = "/mnt/data/downloads/Foundation.S02E08.2160p.WEB.h265-ETHEL[TGx]/Foundation.S02E08.2160p.WEB.h265-ETHEL.mkv"
    # ctx.input_file = "/mnt/data/downloads/Halo.S01.2160p.UHD.BluRay.Remux.HDR.DV.HEVC.Atmos-PmP/Halo.S01E04.Homecoming.2160p.UHD.BluRay.Remux.HDR.DV.HEVC.Atmos-PmP.mkv"
    ctx.output_file = "/home/kokoniara/showsEncode/HALO (2022)/s1/e4/out.webm"
    ctx = do_autocrop(ctx, None)
    print("Crop string: ", ctx.crop_string)
    assert (
        ctx.crop_string == "3840:1920:0:120"
    ), f"Expected 3840:1920:0:120 got {ctx.crop_string}"


def do_cropdetect(path: str = None):
    alabama = PathAlabama(path)
    alabama.check_video()
    fps = Ffmpeg.get_video_frame_rate(alabama)
    length = Ffmpeg.get_video_length(alabama) * fps

    #  create a 10-frame long chunk at 20% 40% 60% 80% of the length
    probe_chunks = []
    for i in range(0, 100, 20):
        first_frame_index = int(length * (i / 100))
        probe_chunks.append(
            ChunkObject(
                path=path,
                last_frame_index=first_frame_index + 10,
                first_frame_index=first_frame_index,
                framerate=fps,
            )
        )

    # function that takes a chunk and output its first cropdetect
    def get_crop(chunk) -> str:
        try:
            return re.search(
                r"-?\d+:-?\d+:-?\d+:-?\d+",
                run_cli(
                    f"{get_binary('ffmpeg')} -hwaccel auto {chunk.get_ss_ffmpeg_command_pair()} -vframes 10 -vf "
                    f"cropdetect -f null -"
                ).get_output(),
            ).group(0)
        except AttributeError:
            return ""

    # get the crops
    crops = [get_crop(chunk) for chunk in probe_chunks]

    # out of the 5 crops, get the most common crop
    most_common_crop = max(set(crops), key=crops.count)

    return most_common_crop
