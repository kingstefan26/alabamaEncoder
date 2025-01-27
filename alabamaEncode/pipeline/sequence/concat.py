import os

from alabamaEncode.scene.concat import VideoConcatenator


def concat(ctx):
    if not ctx.multi_res_pipeline:

        try:
            VideoConcatenator(
                output=ctx.output_file,
                file_with_audio=ctx.input_file,
                audio_param_override=ctx.audio_params,
                start_offset=ctx.start_offset,
                end_offset=ctx.end_offset,
                title=ctx.get_title(),
                encoder_name=ctx.encoder_name,
                mux_audio=ctx.encode_audio,
                subs_file=[ctx.sub_file],
                temp_dir=ctx.temp_folder,
            ).find_files_in_dir(
                folder_path=os.path.join(ctx.temp_folder, "chunks"),
                extension=ctx.get_encoder().get_chunk_file_extension(),
            ).concat_videos()
        except Exception as e:
            print("Concat failed 😷")
            raise e
    return ctx
