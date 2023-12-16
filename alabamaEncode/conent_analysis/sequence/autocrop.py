import os
import time
from typing import List

from alabamaEncode.adaptive.helpers.crop_detect import do_cropdetect
from alabamaEncode.core.bin_utils import get_binary
from alabamaEncode.core.cli_executor import run_cli
from alabamaEncode.core.path import PathAlabama


def do_autocrop(ctx, sequence):
    """
    Does autocrop if needed
    """
    if ctx.auto_crop and ctx.crop_string == "":
        cache_path = f"{ctx.temp_folder}cropdetect.cache"
        if not os.path.exists(cache_path):
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

            with open(cache_path, "w") as f:
                f.write(output)
        else:
            print("Loading autocrop from cache")
            with open(cache_path) as f:
                output = f.read()

        vf = ctx.prototype_encoder.video_filters.split(",")
        for i in range(len(vf)):
            if "crop=" in vf[i]:
                vf[i] = f"crop={output}"
        if "crop=" not in ",".join(vf):
            # add to the start
            vf.insert(0, f"crop={output}")

        ctx.prototype_encoder.video_filters = ",".join(vf)

    return ctx
