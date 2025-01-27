import asyncio
import hashlib
import os
import sys

from tqdm import tqdm

from alabamaEncode.cli.cli_setup.paths import parse_paths
from alabamaEncode.cli.cli_setup.ratecontrol import parse_rd
from alabamaEncode.cli.cli_setup.res_preset import parse_resolution_presets
from alabamaEncode.cli.cli_setup.video_filters import parse_video_filters
from alabamaEncode.conent_analysis.pipelines import (
    get_refine_steps,
    setup_chunk_analyze_chain,
)
from alabamaEncode.conent_analysis.sequence.args_tune import tune_args_for_fdlty_or_apl
from alabamaEncode.conent_analysis.sequence.autocrop import do_autocrop
from alabamaEncode.conent_analysis.sequence.denoise_filtering import setup_denoise
from alabamaEncode.conent_analysis.sequence.encoding_tiles import setup_tiles
from alabamaEncode.conent_analysis.sequence.scene_detection import do_scene_detection
from alabamaEncode.conent_analysis.sequence.scrape_hdr_meta import scrape_hdr_metadata
from alabamaEncode.conent_analysis.sequence.sequence_autograin import setup_autograin
from alabamaEncode.conent_analysis.sequence.setup_chunk_encoder import (
    setup_chunk_encoder,
)
from alabamaEncode.conent_analysis.sequence.setup_chunk_encoders import (
    setup_chunk_encoders,
)
from alabamaEncode.conent_analysis.sequence.taget_ssimdb import setup_ssimdb_target
from alabamaEncode.conent_analysis.sequence.x264_tune import get_ideal_x264_tune
from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.core.extras.vmaf_plot import plot_vmaf
from alabamaEncode.core.extras.ws_update import WebsiteUpdate
from alabamaEncode.core.final_touches import (
    print_stats,
    generate_previews,
    create_torrent_file,
)
from alabamaEncode.metrics.impl.vmaf import (
    download_vmaf_models_wrapper,
)
from alabamaEncode.metrics.metric import Metric
from alabamaEncode.parallel_execution.celery_app import app
from alabamaEncode.parallel_execution.execute_commands import execute_commands
from alabamaEncode.scene.concat import VideoConcatenator


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

        if not os.path.exists(self.ctx.output_file):
            self.websiteUpdate.update_proc_done(10)
            self.websiteUpdate.update_current_step_name("Analyzing content")

            pipeline = [
                do_scene_detection,
                download_vmaf_models_wrapper,
                setup_chunk_analyze_chain,
                setup_chunk_encoder,
                scrape_hdr_metadata,
                tune_args_for_fdlty_or_apl,
                do_autocrop,
                setup_tiles,
                setup_denoise,
                setup_autograin,
                setup_ssimdb_target,
                get_ideal_x264_tune,
                setup_chunk_encoders,
            ]

            for func in pipeline:
                # if async await, if not run normally
                self.ctx = (
                    await func(self.ctx, self.ctx.chunk_sequence)
                    if func.__code__.co_flags & 0x80
                    else func(self.ctx, self.ctx.chunk_sequence)
                )

            self.ctx.get_kv().set_global("quiet_analyzing_content_logs", True)

            self.websiteUpdate.update_proc_done(20)
            self.websiteUpdate.update_current_step_name("Encoding scenes")

            iter_counter = 0
            if self.ctx.dry_run:
                iter_counter = 2

            while self.ctx.chunk_sequence.sequence_integrity_check(
                kv=self.ctx.get_kv()
            ):
                iter_counter += 1
                if iter_counter > 3:
                    print("Integrity check failed 3 times, aborting")
                    quit()

                if len(self.ctx.chunk_jobs) > 0:
                    print(
                        f"Starting encoding of {len(self.ctx.chunk_jobs)} out of {len(self.ctx.chunk_sequence.chunks)} scenes"
                    )
                    saved_progress = self.ctx.get_kv().get_global("pbar_progress")
                    pbar = tqdm(
                        total=sum([c.chunk.length for c in self.ctx.chunk_jobs]),
                        desc="Encoding",
                        unit="frame",
                        dynamic_ncols=True,
                        unit_scale=True,
                        smoothing=0,
                        initial=saved_progress if saved_progress is not None else 0,
                    )

                    saved_total = self.ctx.get_kv().get_global("pbar_total")
                    if saved_total is not None:
                        pbar.total = saved_total

                    saved_estimation = self.ctx.get_kv().get_global("pbar_estimation")
                    if saved_estimation is not None:
                        pbar.set_postfix(estimation=saved_estimation)

                    pbar.refresh()

                    def update_proc_done(num_finished_scenes):
                        already_done = len(self.ctx.chunk_sequence.chunks) - len(
                            self.ctx.chunk_jobs
                        )
                        self.websiteUpdate.update_proc_done(
                            (
                                (already_done + num_finished_scenes)
                                / len(self.ctx.chunk_sequence.chunks)
                            )
                            * 100
                        )

                    try:
                        await asyncio.create_task(
                            execute_commands(
                                use_celery=self.ctx.use_celery,
                                command_objects=self.ctx.chunk_jobs,
                                multiprocess_workers=self.ctx.multiprocess_workers,
                                pin_to_cores=self.ctx.pin_to_cores,
                                finished_scene_callback=update_proc_done,
                                size_estimate_data=(
                                    self.ctx.last_session_encoded_frames,
                                    self.ctx.last_session_size_kb,
                                ),
                                throughput_scaling=self.ctx.throughput_scaling,
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

                for refine_step in get_refine_steps(self.ctx):
                    refine_step(self.ctx, self.ctx.chunk_sequence)

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
                        folder_path=os.path.join(self.ctx.temp_folder, "chunks"),
                        extension=self.ctx.get_encoder().get_chunk_file_extension(),
                    ).concat_videos()
                except Exception as e:
                    print("Concat failed 😷")
                    raise e

            constant_updates.cancel()
        else:
            print("Encoding job already done")

        self.websiteUpdate.update_proc_done(99)
        self.websiteUpdate.update_current_step_name("Final touches")

        if self.ctx.generate_stats:
            print_stats(
                output_folder=self.ctx.output_folder,
                output=self.ctx.output_file,
                title=self.ctx.get_title(),
            )
            target_metric = self.ctx.get_metric_target()[0]
            if self.ctx.calc_final_vmaf and (
                target_metric == Metric.VMAF or target_metric == Metric.XPSNR
            ):
                plot_vmaf(self.ctx, self.ctx.chunk_sequence)

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
