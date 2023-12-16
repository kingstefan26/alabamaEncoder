import asyncio
import os
import random

from alabamaEncode.adaptive.executor import AdaptiveCommand
from alabamaEncode.conent_analysis.sequence_pipeline import run_sequence_pipeline
from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.final_touches import (
    print_stats,
    generate_previews,
    create_torrent_file,
)
from alabamaEncode.core.path import PathAlabama
from alabamaEncode.parallelEncoding.CeleryApp import app
from alabamaEncode.parallelEncoding.execute_commands import execute_commands
from alabamaEncode.scene.concat import VideoConcatenator
from alabamaEncode.scene.sequence import ChunkSequence
from alabamaEncode.scene.split import get_video_scene_list_skinny


class AlabamaEncodingJob:
    def __init__(self, ctx):
        self.ctx = ctx

    def run_pipeline(self):
        if self.ctx.use_celery:
            print("Using celery")
            import socket

            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                # doesn't even have to be reachable
                s.connect(("10.255.255.255", 1))
                host_address = s.getsockname()[0]
            finally:
                s.close()
            print(f"Got lan ip: {host_address}")

            num_workers = app.control.inspect().active_queues()
            if num_workers is None:
                print("No workers detected, please start some")
                quit()
            print(f"Number of available workers: {len(num_workers)}")
        else:
            print(
                f"Using {self.ctx.prototype_encoder.get_enum()} version: {self.ctx.prototype_encoder.get_version()}"
            )

        if not os.path.exists(self.ctx.output_file):
            sequence: ChunkSequence = get_video_scene_list_skinny(
                input_file=self.ctx.input_file,
                cache_file_path=self.ctx.temp_folder + "sceneCache.pt",
                max_scene_length=self.ctx.max_scene_length,
                start_offset=self.ctx.start_offset,
                end_offset=self.ctx.end_offset,
                override_bad_wrong_cache_path=self.ctx.override_scenecache_path_check,
            )
            sequence.setup_paths(
                temp_folder=self.ctx.temp_folder,
                extension=self.ctx.get_encoder().get_chunk_file_extension(),
            )

            run_sequence_pipeline(self.ctx, sequence)
            chunks_sequence = sequence

            iter_counter = 0
            if self.ctx.dry_run:
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
                    command_objects = []
                    ctx = self.ctx

                    for chunk in sequence.chunks:
                        if not chunk.is_done():
                            command_objects.append(AdaptiveCommand(ctx, chunk))

                    # order chunks based on order
                    if ctx.chunk_order == "random":
                        random.shuffle(command_objects)
                    elif ctx.chunk_order == "length_asc":
                        command_objects.sort(key=lambda x: x.job.chunk.length)
                    elif ctx.chunk_order == "length_desc":
                        command_objects.sort(
                            key=lambda x: x.job.chunk.length, reverse=True
                        )
                    elif ctx.chunk_order == "sequential":
                        pass
                    elif ctx.chunk_order == "sequential_reverse":
                        command_objects.reverse()
                    else:
                        raise ValueError(f"Invalid chunk order: {ctx.chunk_order}")

                    if len(command_objects) < 10:
                        ctx.prototype_encoder.threads = os.cpu_count()

                    print(f"Starting encoding of {len(command_objects)} scenes")

                    loop.run_until_complete(
                        execute_commands(
                            ctx.use_celery,
                            command_objects,
                            ctx.multiprocess_workers,
                            pin_to_cores=ctx.pin_to_cores,
                        )
                    )

                except KeyboardInterrupt:
                    print("Keyboard interrupt, stopping")
                    quit()
                finally:
                    loop.stop()

            try:
                VideoConcatenator(
                    output=self.ctx.output_file,
                    file_with_audio=self.ctx.input_file,
                    audio_param_override=self.ctx.audio_params,
                    start_offset=self.ctx.start_offset,
                    end_offset=self.ctx.end_offset,
                    title=self.ctx.title,
                    encoder_name=self.ctx.encoder_name,
                    mux_audio=self.ctx.encode_audio,
                    subs_file=[self.ctx.sub_file],
                ).find_files_in_dir(
                    folder_path=self.ctx.temp_folder,
                    extension=self.ctx.get_encoder().get_chunk_file_extension(),
                ).concat_videos()
            except Exception as e:
                print("Concat failed 😷")
                raise e
        else:
            print("Output file exists 🤑, printing stats")

        print_stats(
            output_folder=self.ctx.output_folder,
            output=self.ctx.output_file,
            input_file=self.ctx.raw_input_file,
            grain_synth=-1,
            title=self.ctx.title,
            cut_intro=(True if self.ctx.start_offset > 0 else False),
            cut_credits=(True if self.ctx.end_offset > 0 else False),
            croped=(True if self.ctx.crop_string != "" else False),
            scaled=(True if self.ctx.scale_string != "" else False),
            tonemaped=(
                True
                if not self.ctx.prototype_encoder.hdr
                and Ffmpeg.is_hdr(PathAlabama(self.ctx.input_file))
                else False
            ),
        )
        if self.ctx.generate_previews:
            print("Generating previews")
            generate_previews(
                input_file=self.ctx.output_file,
                output_folder=self.ctx.output_folder,
                num_previews=4,
                preview_length=5,
            )
            create_torrent_file(
                video=self.ctx.output_file,
                encoder_name=self.ctx.encoder_name,
                output_folder=self.ctx.output_folder,
            )

        print("Cleaning up temp folder 🥺")
        for root, dirs, files in os.walk(self.ctx.temp_folder):
            # remove all folders that contain 'rate_probes'
            for name in dirs:
                if "rate_probes" in name:
                    # remove {rate probe folder}/*.ivf
                    for root2, dirs2, files2 in os.walk(self.ctx.temp_folder + name):
                        for name2 in files2:
                            if name2.endswith(".ivf"):
                                os.remove(self.ctx.temp_folder + name + "/" + name2)
            # remove all *.stat files in tempfolder
            for name in files:
                if name.endswith(".stat"):
                    # try to remove
                    os.remove(self.ctx.temp_folder + name)
        # clean empty folders in the temp folder
        for root, dirs, files in os.walk(self.ctx.temp_folder):
            for name in dirs:
                if len(os.listdir(os.path.join(root, name))) == 0:
                    os.rmdir(os.path.join(root, name))
