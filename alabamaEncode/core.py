import asyncio
import os

from alabamaEncode.adaptive.analyser import analyze_content
from alabamaEncode.alabama import AlabamaContext
from alabamaEncode.ffmpeg import Ffmpeg
from alabamaEncode.final_touches import print_stats, generate_previews, create_torrent_file
from alabamaEncode.parallelEncoding.CeleryApp import app
from alabamaEncode.path import PathAlabama
from alabamaEncode.scene.concat import VideoConcatenator
from alabamaEncode.scene.sequence import ChunkSequence
from alabamaEncode.scene.split import get_video_scene_list_skinny


def encode(ctx):
    chunks_sequence = chunk_and_analyze(ctx)

    encode_chunks(chunks_sequence, ctx)

    merge(ctx)


def encode_chunks(chunks_sequence, ctx):
    iter_counter = 0
    if ctx.dry_run:
        iter_counter = 2
    while chunks_sequence.sequence_integrity_check() is True:
        iter_counter += 1
        if iter_counter > 3:
            print("Integrity check failed 3 times, aborting")
            quit()

        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            loop.run_until_complete(chunks_sequence.process_chunks(ctx=ctx))
        except KeyboardInterrupt:
            print("Keyboard interrupt, stopping")
            quit()
        finally:
            loop.stop()


def merge(ctx):
    try:
        concat = VideoConcatenator(
            output=ctx.output_file,
            file_with_audio=ctx.input_file,
            audio_param_override=ctx.audio_params,
            start_offset=ctx.start_offset,
            end_offset=ctx.end_offset,
            title=ctx.title,
            encoder_name=ctx.encoder_name,
            mux_audio=ctx.encode_audio,
            subs_file=[ctx.sub_file],
        )
        concat.find_files_in_dir(
            folder_path=ctx.temp_folder,
            extension=ctx.get_encoder().get_chunk_file_extension(),
        )
        concat.concat_videos()
    except Exception as e:
        print("Concat at the end failed 😷")
        raise e


def chunk_and_analyze(ctx):
    chunks_sequence: ChunkSequence = get_video_scene_list_skinny(
        input_file=ctx.input_file,
        cache_file_path=ctx.temp_folder + "sceneCache.pt",
        max_scene_length=ctx.max_scene_length,
        start_offset=ctx.start_offset,
        end_offset=ctx.end_offset,
        override_bad_wrong_cache_path=ctx.override_scenecache_path_check,
    )
    chunks_sequence.setup_paths(
        temp_folder=ctx.temp_folder,
        extension=ctx.get_encoder().get_chunk_file_extension(),
    )
    analyze_content(chunks_sequence, ctx)
    return chunks_sequence


def run(ctx: AlabamaContext):
    enc_version = ctx.get_encoder().get_version()
    print(f"Using {ctx.encoder} version: {enc_version}")

    if ctx.use_celery:
        print("Using celery")
        import socket

        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            # doesn't even have to be reachable
            s.connect(("10.255.255.255", 1))
            host_address = s.getsockname()[0]
        except:
            host_address = "127.0.0.1"
        finally:
            s.close()
        print(f"Got lan ip: {host_address}")

        num_workers = app.control.inspect().active_queues()
        if num_workers is None:
            print("No workers detected, please start some")
            quit()
        print(f"Number of available workers: {len(num_workers)}")

    if not os.path.exists(ctx.output_file):
        encode(ctx)
    else:
        print("Output file exists 🤑, printing stats")

    print_stats(
        output_folder=ctx.output_folder,
        output=ctx.output_file,
        config_bitrate=ctx.bitrate,
        input_file=ctx.raw_input_file,
        grain_synth=-1,
        title=ctx.title,
        cut_intro=(True if ctx.start_offset > 0 else False),
        cut_credits=(True if ctx.end_offset > 0 else False),
        croped=(True if ctx.crop_string != "" else False),
        scaled=(True if ctx.scale_string != "" else False),
        tonemaped=(
            True
            if not ctx.hdr and Ffmpeg.is_hdr(PathAlabama(ctx.input_file))
            else False
        ),
    )
    if ctx.generate_previews:
        print("Generating previews")
        generate_previews(
            input_file=ctx.output_file,
            output_folder=ctx.output_folder,
            num_previews=4,
            preview_length=5,
        )
        create_torrent_file(
            video=ctx.output_file,
            encoder_name=ctx.encoder_name,
            output_folder=ctx.output_folder,
        )

    print("Cleaning up temp folder 🥺")
    for root, dirs, files in os.walk(ctx.temp_folder):
        # remove all folders that contain 'rate_probes'
        for name in dirs:
            if "rate_probes" in name:
                # remove {rate probe folder}/*.ivf
                for root2, dirs2, files2 in os.walk(ctx.temp_folder + name):
                    for name2 in files2:
                        if name2.endswith(".ivf"):
                            try:
                                os.remove(ctx.temp_folder + name + "/" + name2)
                            except:
                                pass
        # remove all *.stat files in tempfolder
        for name in files:
            if name.endswith(".stat"):
                # try to remove
                try:
                    os.remove(ctx.temp_folder + name)
                except:
                    pass
    # clean empty folders in the temp folder
    for root, dirs, files in os.walk(ctx.temp_folder):
        for name in dirs:
            if len(os.listdir(os.path.join(root, name))) == 0:
                os.rmdir(os.path.join(root, name))
