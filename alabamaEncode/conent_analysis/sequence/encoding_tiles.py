from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.encoder.codec import Codec
from alabamaEncode.scene.sequence import ChunkSequence


def setup_tiles(ctx: AlabamaContext, sequence: ChunkSequence):
    """
    Sets up the tiles based on the resolution
    stolen from the one and only autocompressor.com's source code.
    🤑
    """
    if ctx.prototype_encoder.get_codec() == Codec.av1 and not ctx.multi_res_pipeline:
        if (
            ctx.prototype_encoder.tile_cols == -1
            and ctx.prototype_encoder.tile_rows == -1
        ):
            width, height = ctx.get_output_res()

            def calculate_tiles(video_width, video_height, target_pixels_per_tile):
                # when target_pixels_per_tile is 2,000,000 -> 1 tile at 1080p
                # when target_pixels_per_tile is 1,000,000 -> 2 tiles at 1080p
                rowsl = 0
                colsl = 0
                ctpx = video_width * video_height
                # current tile pixels, starts at the full size of the video
                # we subdivide until <4/3 of targetPixelsPerTile
                ctar = video_width / video_height
                # current tile aspect ratio, we subdivide into cols if >1 and rows if ≤1
                while ctpx >= target_pixels_per_tile * 4 / 3:
                    if ctar > 1:
                        # Subdivide into columns, add 1 to colsl and halve ctar, then halve ctpx
                        colsl += 1
                        ctar /= 2
                        ctpx /= 2
                    else:
                        # Subdivide into rows, add 1 to rowsl and double ctar, then halve ctpx
                        rowsl += 1
                        ctar *= 2
                        ctpx /= 2
                return {
                    "tileRowsLog2": rowsl,
                    "tileColsLog2": colsl,
                    "tileRows": 2**rowsl,
                    "tileCols": 2**colsl,
                }

            tile_info = calculate_tiles(width, height, 1_666_666)
            ctx.log(
                f"Calculated literal tile cols: {tile_info['tileCols']}; literal tile rows: {tile_info['tileRows']}",
                category="analyzing_content_logs"
            )
            ctx.prototype_encoder.tile_rows = tile_info["tileRowsLog2"]
            ctx.prototype_encoder.tile_cols = tile_info["tileColsLog2"]

    return ctx
