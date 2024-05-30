import os

from alabamaEncode.conent_analysis.opinionated_vmaf import get_vmaf_list
from alabamaEncode.conent_analysis.refine_step import RefineStep
from alabamaEncode.core.util.bin_utils import get_binary
from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.util.path import PathAlabama
from alabamaEncode.scene.concat import VideoConcatenator


class MutliResPackage(RefineStep):
    def __call__(self, ctx, sequence):
        final_paths = ctx.get_kv().get("multires_final_paths", "final_paths")
        if final_paths is None:
            print("Not packaging, final paths not done")
            return

        codec = ctx.prototype_encoder.get_codec()
        vmafs = get_vmaf_list(codec)

        for chunk in sequence.chunks:
            for vmaf in vmafs:
                chunk_vmaf_path = ctx.get_kv().get(
                    "multires_final_paths", f"{chunk.chunk_index}_{vmaf}"
                )
                if chunk_vmaf_path is None or not os.path.exists(chunk_vmaf_path):
                    print("Not packaging, final paths not done")
                    return

        concated_files = []

        ctc = VideoConcatenator(
            output="",
            file_with_audio=ctx.input_file,
            start_offset=ctx.start_offset,
            end_offset=ctx.end_offset,
            title=ctx.get_title(),
            encoder_name=ctx.encoder_name,
            mux_audio=False,
            subs_file=[],
        )

        for path in final_paths:
            vmaf_target = path["vmaf_target"]
            print(f"\n vmaf_target: {vmaf_target}")
            # concat
            out_path = os.path.join(
                ctx.output_folder,
                f"vmaf{vmaf_target}_{path['res']}.mp4",
            )
            ctc.output = out_path
            concated_files += [out_path]

            ctc.files = []
            for c in sequence.chunks:
                chunk_vmaf_path = ctx.get_kv().get(
                    "multires_final_paths", f"{c.chunk_index}_{vmaf_target}"
                )
                ctc.files += [chunk_vmaf_path]

            ctc.concat_videos()

        print("\n encoding audio tracks")
        audio_track_96_path = os.path.join(
            ctx.output_folder,
            f"audio_track_96.mp4",
        )
        ctc.audio_param_override = "-c:a libopus -ac 2 -b:a 96k -vbr on"
        ctc.output = audio_track_96_path
        ctc.audio_only = True
        ctc.concat_videos()

        audio_track_128_path = os.path.join(
            ctx.output_folder,
            f"audio_track_128.mp4",
        )
        ctc.audio_param_override = "-c:a libopus -ac 2 -b:a 128k -vbr on"
        ctc.output = audio_track_128_path
        ctc.audio_only = True
        ctc.concat_videos()

        # example cli:
        # packager \
        # in=64k.webm,stream=audio,output=64.webm \
        # in=256k.webm,stream=audio,output=256.webm \
        # in=og_480p.webm,stream=video,output=480p.webm \
        # in=og_1080p.webm,stream=video,output=1080p.webm \
        # in=og_480p.webm,stream=video,output=480p_trick.webm,trick_play_factor=1 \
        # in=og_1080p.webm,stream=video,output=1080p_trick.webm,trick_play_factor=1 \
        # --mpd_output ./stream/stream.mpd

        files_cli = ""
        for file in concated_files:
            files_cli += f" in={file},stream=video,output={file} "

        trick_path = os.path.join(
            ctx.output_folder,
            f"trick.mp4",
        )
        trick = f" in={concated_files[-1]},stream=video,output={trick_path},trick_play_factor=1 "
        audio = (
            f" in={audio_track_96_path},stream=audio,output={audio_track_96_path} "
            f" in={audio_track_128_path},stream=audio,output={audio_track_128_path}"
        )

        print("\n\n")
        final_cli = (
            f"{get_binary('packager')} {files_cli} {trick} {audio}"
            f" --segment_duration 3 "
            f" --mpd_output {ctx.output_file}"
        )
        print("Running final cli:")
        print(final_cli)
        os.system(final_cli)

        stats_content = ""
        for path in final_paths:
            out_path = PathAlabama(
                os.path.join(
                    ctx.output_folder,
                    f"vmaf{path['vmaf_target']}_{path['res']}.mp4",
                )
            )
            bitrate = int(Ffmpeg.get_total_bitrate(out_path) / 1000)
            stats_content += (
                f"vmaf {path['vmaf_target']} res {path['res']} bitrate {bitrate}\n"
            )

        # audio track
        bitrate = int(Ffmpeg.get_total_bitrate(PathAlabama(audio_track_96_path)) / 1000)
        stats_content += f"audio bitrate {bitrate}k\n"

        bitrate = int(
            Ffmpeg.get_total_bitrate(PathAlabama(audio_track_128_path)) / 1000
        )
        stats_content += f"audio bitrate {bitrate}k\n"

        with open(os.path.join(ctx.output_folder, "stats.txt"), "w") as f:
            f.write(stats_content)
