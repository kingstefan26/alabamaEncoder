#!/usr/bin/python
import asyncio
import atexit
import os
import pickle
import sys
import time

from alabamaEncode.adaptive.analyser import analyze_content
from alabamaEncode.alabama import AlabamaContext, setup_context
from alabamaEncode.ffmpeg import Ffmpeg
from alabamaEncode.final_touches import (
    print_stats,
    generate_previews,
    create_torrent_file,
)
from alabamaEncode.parallelEncoding.CeleryApp import app
from alabamaEncode.parallelEncoding.worker import worker
from alabamaEncode.path import PathAlabama
from alabamaEncode.scene.concat import VideoConcatenator
from alabamaEncode.scene.sequence import ChunkSequence
from alabamaEncode.scene.split import get_video_scene_list_skinny

runtime = -1
runtime_file = ""


@atexit.register
def at_exit():
    global runtime
    global runtime_file
    if runtime != -1:
        current_session_runtime = time.time() - runtime

        saved_runtime = 0
        try:
            if os.path.exists(runtime_file):
                with open(runtime_file) as f:
                    saved_runtime = float(f.read())
        except:
            pass
        print(
            f"Current Session Runtime: {current_session_runtime}, Runtime From Previous Sessions: {saved_runtime}, Total Runtime: {current_session_runtime + saved_runtime}"
        )

        try:
            with open(runtime_file, "w") as f:
                f.write(str(current_session_runtime + saved_runtime))
        except:
            pass


def clean_rate_probes(tempfolder: str):
    print("removing rate probe folders owo 🥺")
    for root, dirs, files in os.walk(tempfolder):
        # remove all folders that contain 'rate_probes'
        for name in dirs:
            if "rate_probes" in name:
                # remove {rate probe folder}/*.ivf
                for root2, dirs2, files2 in os.walk(tempfolder + name):
                    for name2 in files2:
                        if name2.endswith(".ivf"):
                            try:
                                os.remove(tempfolder + name + "/" + name2)
                            except:
                                pass
        # remove all *.stat files in tempfolder
        for name in files:
            if name.endswith(".stat"):
                # try to remove
                try:
                    os.remove(tempfolder + name)
                except:
                    pass

    # clean empty folders in the temp folder
    for root, dirs, files in os.walk(tempfolder):
        for name in dirs:
            if len(os.listdir(os.path.join(root, name))) == 0:
                os.rmdir(os.path.join(root, name))


def main():
    """
    Main entry point
    """
    global runtime
    runtime = time.time()

    ctx: [AlabamaContext | None] = None

    if len(sys.argv) > 1:
        match sys.argv[1]:
            case "clear":
                # if a user does 'python __main__.py clear' then clear the celery queue
                print("Clearing celery queue")
                app.control.purge()
                quit()
            case "worker":
                worker()
            case "resume":
                # unpickle ctx from the file "alabamaResume", if dosent exist in current dir quit
                if os.path.exists("alabamaResume"):
                    ctx = pickle.load(open("alabamaResume", "rb"))
                    print("Resuming from alabamaResume")
                else:
                    print("No resume file found in curr dir")
                    quit()

    if ctx is None:
        ctx = setup_context()
        # save ctx to file "alabamaResume" at working dir
        pickle.dump(ctx, open("alabamaResume", "wb"))
    else:
        # we loaded the ctx from a file, so we need to re-run the pre_run_check
        ctx.pre_run_check()

    global runtime_file
    runtime_file = ctx.temp_folder + "runtime.txt"

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

    clean_rate_probes(ctx.temp_folder)

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

    if not os.path.exists(ctx.output_file):
        analyze_content(chunks_sequence, ctx)

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
    clean_rate_probes(ctx.temp_folder)
    quit()


if __name__ == "__main__":
    main()
