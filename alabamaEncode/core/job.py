import asyncio
import hashlib
import os
import random
import sys

from tqdm import tqdm

from alabamaEncode.cli.cli_setup.paths import parse_paths
from alabamaEncode.cli.cli_setup.ratecontrol import parse_rd
from alabamaEncode.cli.cli_setup.res_preset import parse_resolution_presets
from alabamaEncode.cli.cli_setup.video_filters import parse_video_filters
from alabamaEncode.conent_analysis.opinionated_vmaf import (
    get_vmaf_list,
)
from alabamaEncode.conent_analysis.pipelines import (
    run_sequence_pipeline,
    get_refine_steps,
)
from alabamaEncode.core.chunk_job import ChunkEncoder
from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.core.extras.vmaf_plot import plot_vmaf
from alabamaEncode.core.extras.ws_update import WebsiteUpdate
from alabamaEncode.core.final_touches import (
    print_stats,
    generate_previews,
    create_torrent_file,
)
from alabamaEncode.metrics.impl.vmaf import download_vmaf_models
from alabamaEncode.metrics.metric import Metric
from alabamaEncode.parallel_execution.celery_app import app
from alabamaEncode.parallel_execution.execute_commands import execute_commands
from alabamaEncode.scene.annel import annealing
from alabamaEncode.scene.concat import VideoConcatenator
from alabamaEncode.scene.scene_detection import scene_detect
from alabamaEncode.scene.sequence import ChunkSequence


class AlabamaEncodingJob:
    def __init__(self, ctx):
        self.ctx = ctx
        self.websiteUpdate = WebsiteUpdate(ctx)
        self.finished_callback = None

        self.serialise_folder = self.get_serialise_folder()

        sha1 = hashlib.sha1()
        sha1.update(str.encode(self.ctx.get_title()))
        hash_as_hex = sha1.hexdigest()
        title_hash = int(hash_as_hex, 16) % sys.maxsize
        self.serialise_file = os.path.join(
            self.serialise_folder,
            f"{title_hash}" f".json",
        )

    @staticmethod
    def get_serialise_folder():
        serialise_folder = os.path.expanduser("~/.alabamaEncoder/jobs")
        if not os.path.exists(serialise_folder):
            os.makedirs(serialise_folder)
        return serialise_folder

    @staticmethod
    def get_saved_serialised_jobs():
        for file in os.listdir(AlabamaEncodingJob.get_serialise_folder()):
            with open(
                os.path.join(AlabamaEncodingJob.get_serialise_folder(), file)
            ) as f:
                yield f.read()

    def save(self):
        with open(self.serialise_file, "w") as f:
            f.write(self.ctx.to_json())

    def delete(self):
        if os.path.exists(self.serialise_file):
            os.remove(self.serialise_file)

    @staticmethod
    def load_from_file(json_job):
        ctx = AlabamaContext().from_json(json_job)
        creation_pipeline = [
            parse_paths,
            parse_rd,
            parse_resolution_presets,
            parse_video_filters,
        ]
        for pipeline_item in creation_pipeline:
            ctx = pipeline_item(ctx)

        return AlabamaEncodingJob(ctx)

    def encode_finished(self):
        if self.ctx.multi_res_pipeline:
            return os.path.exists(self.ctx.output_file)
            # TODO: do a paranoid check for all files
        else:
            return os.path.exists(self.ctx.output_file)

    async def run_pipeline(self):
        self.save()

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
                f"Using {self.ctx.prototype_encoder.get_pretty_name()} version: {self.ctx.prototype_encoder.get_version()}"
            )

        constant_updates = asyncio.create_task(self.websiteUpdate.constant_updates())
        self.websiteUpdate.update_current_step_name("Running scene detection")

        sequence = self.prepare_sequence()

        if not self.encode_finished():
            self.websiteUpdate.update_proc_done(10)
            self.websiteUpdate.update_current_step_name("Analyzing content")
            download_vmaf_models()
            await run_sequence_pipeline(self.ctx, sequence)
            self.ctx.get_kv().set_global("quiet_analyzing_content_logs", True)

            self.websiteUpdate.update_proc_done(20)
            self.websiteUpdate.update_current_step_name("Encoding scenes")

            iter_counter = 0
            if self.ctx.dry_run:
                iter_counter = 2

            while sequence.sequence_integrity_check(kv=self.ctx.get_kv()):
                iter_counter += 1
                if iter_counter > 3:
                    print("Integrity check failed 3 times, aborting")
                    quit()

                ctx = self.ctx
                frames_encoded_so_far = 0
                size_kb_so_far = 0

                command_objects = []

                def is_chunk_done(_chunk):
                    if ctx.multi_res_pipeline:
                        enc = ctx.get_encoder()
                        vmafs = get_vmaf_list(enc.get_codec())

                        for vmaf in vmafs:
                            output_path = (
                                f"{ctx.temp_folder}/"
                                f"{_chunk.chunk_index}_{vmaf}.{enc.get_chunk_file_extension()}"
                            )
                            if not os.path.exists(output_path):
                                return False

                        return True
                    else:
                        return _chunk.is_done(kv=ctx.get_kv())

                for chunk in sequence.chunks:
                    if not is_chunk_done(chunk):
                        command_objects.append(ChunkEncoder(ctx, chunk))
                    else:
                        frames_encoded_so_far += chunk.get_frame_count()
                        size_kb_so_far += chunk.get_filesize() / 1000

                threads = os.cpu_count()
                if len(command_objects) < threads:
                    ctx.prototype_encoder.threads = int(threads / len(command_objects))

                # order chunks based on order
                if ctx.chunk_order == "random":
                    random.shuffle(command_objects)
                elif ctx.chunk_order == "length_asc":
                    command_objects.sort(key=lambda x: x.job.chunk.length)
                elif ctx.chunk_order == "length_desc":
                    command_objects.sort(key=lambda x: x.job.chunk.length, reverse=True)
                elif ctx.chunk_order == "sequential":
                    pass
                elif ctx.chunk_order == "sequential_reverse":
                    command_objects.reverse()
                elif ctx.chunk_order == "even":
                    command_objects = annealing(command_objects, 1000)
                else:
                    raise ValueError(f"Invalid chunk order: {ctx.chunk_order}")

                if ctx.throughput_scaling:
                    # make the chunk length distribution homogenous
                    command_objects = annealing(command_objects, 1000)

                print(
                    f"Starting encoding of {len(command_objects)} out of {len(sequence.chunks)} scenes"
                )

                def update_proc_done(num_finished_scenes):
                    already_done = len(sequence.chunks) - len(command_objects)
                    # map 20 to 95% as the space where the scenes are encoded
                    self.websiteUpdate.update_proc_done(
                        20
                        + (already_done + num_finished_scenes)
                        / len(sequence.chunks)
                        * 75
                    )

                kv = self.ctx.get_kv()
                saved_progress = kv.get_global("pbar_progress")

                pbar = tqdm(
                    total=sum([c.chunk.length for c in command_objects]),
                    desc="Encoding",
                    unit="frame",
                    dynamic_ncols=True,
                    unit_scale=True,
                    smoothing=0.2,
                    initial=saved_progress if saved_progress is not None else 0,
                )

                saved_total = kv.get_global("pbar_total")
                if saved_total is not None:
                    pbar.total = saved_total

                saved_estimation = kv.get_global("pbar_estimation")
                if saved_estimation is not None:
                    pbar.set_postfix(estimation=saved_estimation)

                pbar.refresh()

                if len(command_objects) == 0:
                    print("Nothing to encode, skipping")
                else:
                    try:
                        await asyncio.create_task(
                            execute_commands(
                                ctx.use_celery,
                                command_objects,
                                ctx.multiprocess_workers,
                                pin_to_cores=ctx.pin_to_cores,
                                finished_scene_callback=update_proc_done,
                                size_estimate_data=(
                                    frames_encoded_so_far,
                                    size_kb_so_far,
                                ),
                                throughput_scaling=ctx.throughput_scaling,
                                pbar=pbar,
                            )
                        )
                    except (KeyboardInterrupt, asyncio.exceptions.CancelledError):
                        print("Keyboard interrupt, stopping")
                        # kill all async tasks
                        pbar.close()
                        for task in asyncio.all_tasks():
                            task.cancel()

                        # save pbar progress in kv
                        kv = self.ctx.get_kv()
                        kv.set_global("pbar_progress", pbar.n)
                        if kv.get_global("pbar_total") is None:
                            kv.set_global("pbar_total", pbar.total)
                        kv.set_global("pbar_estimation", pbar.postfix.get("estimation"))
                        quit()

                refine_steps = get_refine_steps(ctx)
                for step in refine_steps:
                    step(ctx, sequence)

            if not self.ctx.multi_res_pipeline:
                self.websiteUpdate.update_proc_done(95)
                self.websiteUpdate.update_current_step_name("Concatenating scenes")

                try:
                    VideoConcatenator(
                        output=self.ctx.output_file,
                        file_with_audio=self.ctx.input_file,
                        audio_param_override=self.ctx.audio_params,
                        start_offset=self.ctx.start_offset,
                        end_offset=self.ctx.end_offset,
                        title=self.ctx.get_title(),
                        encoder_name=self.ctx.encoder_name,
                        mux_audio=self.ctx.encode_audio,
                        subs_file=[self.ctx.sub_file],
                        temp_dir=self.ctx.temp_folder,
                    ).find_files_in_dir(
                        folder_path=self.ctx.temp_folder,
                        extension=self.ctx.get_encoder().get_chunk_file_extension(),
                    ).concat_videos()
                except Exception as e:
                    print("Concat failed 😷")
                    raise e
            constant_updates.cancel()
        else:
            print("Output file already exists")

        self.websiteUpdate.update_proc_done(99)
        self.websiteUpdate.update_current_step_name("Final touches")

        if self.ctx.generate_stats:
            print_stats(
                output_folder=self.ctx.output_folder,
                output=self.ctx.output_file,
                # input_file=self.ctx.raw_input_file,
                # grain_synth=self.ctx.prototype_encoder.grain_synth,
                title=self.ctx.get_title(),
                # cut_intro=(True if self.ctx.start_offset > 0 else False),
                # cut_credits=(True if self.ctx.end_offset > 0 else False),
                # croped=(True if self.ctx.crop_string != "" else False),
                # scaled=(True if self.ctx.scale_string != "" else False),
                # tonemaped=(
                #     True
                #     if not self.ctx.prototype_encoder.hdr
                #     and Ffmpeg.is_hdr(PathAlabama(self.ctx.input_file))
                #     else False
                # ),
            )
            if (
                self.ctx.calc_final_vmaf
                and self.ctx.get_metric_target()[0] == Metric.VMAF
            ):
                plot_vmaf(self.ctx, sequence)

        if self.ctx.generate_previews:
            generate_previews(
                input_file=self.ctx.output_file, output_folder=self.ctx.output_folder
            )
            create_torrent_file(
                video=self.ctx.output_file,
                encoder_name=self.ctx.encoder_name,
                output_folder=self.ctx.output_folder,
            )

        # TODO cleanup right in multiencode
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

        self.websiteUpdate.update_proc_done(100)
        self.websiteUpdate.update_current_step_name("Done")
        if self.finished_callback is not None:
            self.finished_callback()

        self.delete()

    def prepare_sequence(self):
        sequence: ChunkSequence = scene_detect(
            input_file=self.ctx.input_file,
            cache_file_path=self.ctx.temp_folder + "scene_cache.json",
            max_scene_length=self.ctx.max_scene_length,
            start_offset=self.ctx.start_offset,
            end_offset=self.ctx.end_offset,
            override_bad_wrong_cache_path=self.ctx.override_scenecache_path_check,
            static_length=self.ctx.statically_sized_scenes,
            static_length_size=self.ctx.max_scene_length,
            scene_merge=self.ctx.scene_merge,
        )
        sequence.setup_paths(
            temp_folder=self.ctx.temp_folder,
            extension=self.ctx.get_encoder().get_chunk_file_extension(),
        )
        self.ctx.total_chunks = len(sequence.chunks)
        return sequence
