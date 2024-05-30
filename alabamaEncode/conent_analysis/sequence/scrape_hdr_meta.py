import json
import os

from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.util.path import PathAlabama
from alabamaEncode.encoder.impl.Svtenc import EncoderSvt
from alabamaEncode.encoder.impl.X264 import EncoderX264
from alabamaEncode.scene.sequence import ChunkSequence


def scrape_hdr_metadata(ctx: AlabamaContext, sequence: ChunkSequence):
    """
    Scrapes HDR metadata from the input file
    """
    if ctx.prototype_encoder.hdr and (
        isinstance(ctx.prototype_encoder, EncoderSvt)
        or isinstance(ctx.prototype_encoder, EncoderX264)
    ):
        if not Ffmpeg.is_hdr(PathAlabama(ctx.raw_input_file)):
            print("Input file is not HDR, disabling HDR mode")
            ctx.prototype_encoder.hdr = False
            return ctx

        cache_path = f"{ctx.temp_folder}hdr.cache"

        if not os.path.exists(cache_path):
            print("Running auto HDR10")
            obj = Ffmpeg.get_first_frame_data(PathAlabama(ctx.raw_input_file))
            color_space = obj["color_space"]
            if "bt2020nc" in color_space:
                color_space = "bt2020-ncl"

            if ctx.prototype_encoder.matrix_coefficients == "bt709":
                ctx.prototype_encoder.matrix_coefficients = color_space
                print(
                    f"Setting color space to {ctx.prototype_encoder.matrix_coefficients}"
                )

            if ctx.prototype_encoder.color_primaries == "bt709":
                ctx.prototype_encoder.color_primaries = obj["color_primaries"]
                print(
                    f"Setting color primaries to {ctx.prototype_encoder.color_primaries}"
                )

            if ctx.prototype_encoder.transfer_characteristics == "bt709":
                ctx.prototype_encoder.transfer_characteristics = obj["color_transfer"]
                print(
                    f"Setting transfer characteristics to {ctx.prototype_encoder.transfer_characteristics}"
                )

            ctx.prototype_encoder.chroma_sample_position = obj["chroma_location"]
            print(
                f"Setting chroma sample position to {ctx.prototype_encoder.chroma_sample_position}"
            )

            for side_data in obj["side_data_list"]:
                if side_data["side_data_type"] == "Content light level metadata":
                    if ctx.prototype_encoder.maximum_content_light_level == "":
                        ctx.prototype_encoder.maximum_content_light_level = side_data[
                            "max_content"
                        ]
                    if ctx.prototype_encoder.maximum_frame_average_light_level == "":
                        ctx.prototype_encoder.maximum_frame_average_light_level = (
                            side_data["max_average"]
                        )
                    print(
                        f"Setting max content light level to {ctx.prototype_encoder.maximum_content_light_level}"
                    )
                    print(
                        f"Setting max frame average light level to "
                        f"{ctx.prototype_encoder.maximum_frame_average_light_level}"
                    )
                if side_data["side_data_type"] == "Mastering display metadata":

                    def split_and_divide(spltting) -> float:
                        spl = spltting.split("/")
                        return int(spl[0]) / int(spl[1])

                    red_x = split_and_divide(side_data["red_x"])
                    red_y = split_and_divide(side_data["red_y"])
                    green_x = split_and_divide(side_data["green_x"])
                    green_y = split_and_divide(side_data["green_y"])
                    blue_x = split_and_divide(side_data["blue_x"])
                    blue_y = split_and_divide(side_data["blue_y"])
                    white_point_x = split_and_divide(side_data["white_point_x"])
                    white_point_y = split_and_divide(side_data["white_point_y"])
                    min_luminance = split_and_divide(side_data["min_luminance"])
                    max_luminance = split_and_divide(side_data["max_luminance"])
                    # G(x,y)B(x,y)R(x,y)WP(x,y)L(max,min)
                    ctx.prototype_encoder.svt_master_display = (
                        f"G({green_x},{green_y})B({blue_x},{blue_y})R({red_x},{red_y})"
                        f"WP({white_point_x},{white_point_y})L({max_luminance},{min_luminance})"
                    )

                    print(
                        f"Setting svt master display to {ctx.prototype_encoder.svt_master_display}"
                    )

            cache_obj = {
                "matrix_coefficients": ctx.prototype_encoder.matrix_coefficients,
                "color_primaries": ctx.prototype_encoder.color_primaries,
                "transfer_characteristics": ctx.prototype_encoder.transfer_characteristics,
                "chroma_sample_position": ctx.prototype_encoder.chroma_sample_position,
                "maximum_content_light_level": ctx.prototype_encoder.maximum_content_light_level,
                "maximum_frame_average_light_level": ctx.prototype_encoder.maximum_frame_average_light_level,
                "svt_master_display": ctx.prototype_encoder.svt_master_display,
            }

            # save as json
            with open(cache_path, "w") as f:
                f.write(json.dumps(cache_obj))
        else:
            print("Loading HDR10 metadata from cache")
            with open(cache_path) as f:
                cache_obj = json.loads(f.read())
            ctx.prototype_encoder.matrix_coefficients = cache_obj["matrix_coefficients"]
            ctx.prototype_encoder.color_primaries = cache_obj["color_primaries"]
            ctx.prototype_encoder.transfer_characteristics = cache_obj[
                "transfer_characteristics"
            ]
            ctx.prototype_encoder.chroma_sample_position = cache_obj[
                "chroma_sample_position"
            ]
            ctx.prototype_encoder.maximum_content_light_level = cache_obj[
                "maximum_content_light_level"
            ]
            ctx.prototype_encoder.maximum_frame_average_light_level = cache_obj[
                "maximum_frame_average_light_level"
            ]
            ctx.prototype_encoder.svt_master_display = cache_obj["svt_master_display"]

    return ctx


if __name__ == "__main__":
    ctx = AlabamaContext()
    ctx.prototype_encoder.hdr = True
    # ctx.raw_input_file = "/mnt/data/downloads/Halo.S01.2160p.UHD.BluRay.Remux.HDR.DV.HEVC.Atmos-PmP/Halo.S01E04.Homecoming.2160p.UHD.BluRay.Remux.HDR.DV.HEVC.Atmos-PmP.mkv"
    ctx.raw_input_file = "/mnt/data/downloads/Silo.S01E02.HDR.2160p.WEB.H265-GGEZ[rarbg]/silo.s01e02.hdr.2160p.web.h265-ggez.mkv"
    print(f"Extracting HDR10 metadata 🤩😳 for {os.path.basename(ctx.raw_input_file)}")
    ctx = scrape_hdr_metadata(ctx)

    print("matrix_coefficients", ctx.prototype_encoder.matrix_coefficients)
    print("color_primaries", ctx.prototype_encoder.color_primaries)
    print("transfer_characteristics", ctx.prototype_encoder.transfer_characteristics)
    print("chroma_sample_position", ctx.prototype_encoder.chroma_sample_position)
    print("max_content", ctx.prototype_encoder.maximum_content_light_level)
    print("max_average", ctx.prototype_encoder.maximum_frame_average_light_level)
    print("svt master display: ", ctx.prototype_encoder.svt_master_display)
