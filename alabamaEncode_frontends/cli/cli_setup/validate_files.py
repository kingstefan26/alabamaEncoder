from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.util.path import PathAlabama


def validate_input(ctx):
    try:
        tracks = Ffmpeg.get_tracks(PathAlabama(ctx.raw_input_file))
        video_track = None
        for track in tracks:
            if track["codec_type"] == "video":
                video_track = track
                break

        if video_track is None:
            print("Cant find video track in input file")
            quit()

        if video_track["codec_name"] == "vc1":
            print(
                "Input file is VC1, VC1 ffmpeg seeking is broken, you'll need encode a lossless proxy to fix this"
            )
            quit()

        hdr = True
        if 'color_transfer' not in video_track:
            hdr = False
        else:
            if (
                "bt709" in video_track["color_transfer"]
                or "unknown" in video_track["color_transfer"]
            ):
                hdr = False

        dem, num = video_track["avg_frame_rate"].split("/")
        fps_rounded = "{:.2f}".format(float(dem) / float(num))
        vid_bitrate = ctx.get_kv().get_global("video_bitrate_formatted")
        if vid_bitrate is None:
            print("Getting source bitrate...")
            vid_bitrate = "{:.2f}".format(
                (
                    Ffmpeg.get_source_bitrates(
                        PathAlabama(ctx.raw_input_file), calculate_audio=False
                    )[0]
                    / 1000
                )
            )
            ctx.get_kv().set_global("video_bitrate_formatted", vid_bitrate)
        codec = video_track['codec_name'].upper()
        print(
            f"Input Video: {video_track['width']}x{video_track['height']} @ {fps_rounded} fps, {video_track['pix_fmt'].upper()}, {'HDR' if hdr else 'SDR'}, {vid_bitrate} Kb/s, {codec}"
        )

    except Exception as e:
        print(f'Input file parsing failed: "{e}", is it a valid video file?')
        quit()
    return ctx
