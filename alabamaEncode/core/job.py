import asyncio
import hashlib
import json
import os
import random
import socket
import sys
import time

import psutil
import requests
from tqdm import tqdm

from alabamaEncode.conent_analysis.opinionated_vmaf import (
    get_vmaf_list,
)
from alabamaEncode.conent_analysis.pipelines import (
    run_sequence_pipeline,
    get_refine_steps,
)
from alabamaEncode.core.alabama import AlabamaContext
from alabamaEncode.core.chunk_job import ChunkEncoder
from alabamaEncode.core.ffmpeg import Ffmpeg
from alabamaEncode.core.final_touches import (
    print_stats,
    generate_previews,
    create_torrent_file,
)
from alabamaEncode.core.path import PathAlabama
from alabamaEncode.core.ws_update import WebsocketServer
from alabamaEncode.parallelEncoding.CeleryApp import app
from alabamaEncode.parallelEncoding.execute_commands import execute_commands
from alabamaEncode.scene.concat import VideoConcatenator
from alabamaEncode.scene.sequence import ChunkSequence
from alabamaEncode.scene.split import get_video_scene_list_skinny
from alabamaEncode_frontends.cli.cli_setup.paths import parse_paths
from alabamaEncode_frontends.cli.cli_setup.ratecontrol import parse_rd
from alabamaEncode_frontends.cli.cli_setup.res_preset import parse_resolution_presets
from alabamaEncode_frontends.cli.cli_setup.video_filters import parse_video_filters


class AlabamaEncodingJob:
    def __init__(self, ctx):
        self.ctx = ctx
        self.current_step_callback = None
        self.proc_done_callback = None
        self.finished_callback = None
        self.proc_done = 0
        self.current_step_name = "idle"
        self.serialise_folder = self.get_serialise_folder()
        sha1 = hashlib.sha1()
        sha1.update(
            str.encode(
                self.ctx.title
                if self.ctx.title != ""
                else os.path.basename(self.ctx.output_file)
            )
        )
        hash_as_hex = sha1.hexdigest()
        # convert the hex back to int and restrict it to the relevant int range
        title_hash = int(hash_as_hex, 16) % sys.maxsize
        self.serialise_file = os.path.join(
            self.serialise_folder,
            f"{title_hash}" f".json",
        )
        self.ws_server = None

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

    def is_done(self):
        return self.proc_done == 100

    last_update = None
    update_proc_throttle = 0
    update_max_freq_sec = 1600

    async def update_website(self):
        api_url = os.environ.get("status_update_api_url", "")
        token = os.environ.get("status_update_api_token", "")
        if api_url != "":
            if token == "":
                print("Url is set, but token is not, not updating status api")
                return

            if self.ctx.title == "":
                print("Url is set, but title is not, not updating status api")
                return

            should_update_api = False

            if time.time() - self.update_proc_throttle > self.update_max_freq_sec:
                self.update_proc_throttle = time.time()
                should_update_api = True

            #         curl -X POST -d '{"action":"update","data":{"img":"https://domain.com/poster.avif","status":100,
            #         "title":"Show 2024 E01S01","phase":"Done"}}'
            #         -H 'Authorization: Bearer token' 'https://domain.com/update'

            status_data = {
                "action": "update",
                "data": {
                    "img": self.ctx.poster_url,
                    "status": round(self.proc_done, 1),  # rounded
                    "title": self.ctx.title,
                    "phase": self.current_step_name,
                },
            }

            if self.last_update == status_data:
                return

            self.last_update = status_data

            if should_update_api:
                try:
                    requests.post(
                        api_url + "/statuses/update",
                        json=status_data,
                        headers={"Authorization": f"Bearer {token}"},
                    )
                except Exception as e:
                    self.ctx.log(f"Failed to update status api: {e}")

                self.ctx.log("Updated encode status api")

            #  curl -X POST -d '{"action":"update","data":{"id":"kokoniara-B550MH",
            #  "status":"working on title", "utilization":95}}' -H 'Authorization: Bearer token'
            #  'http://domain.com/workers/update'

            worker_data = {
                "action": "update",
                "data": {
                    "id": (socket.gethostname()),
                    "status": f"Working on {self.ctx.title}",
                    "utilization": int(psutil.cpu_percent()),
                    "ws_ip": self.ws_server.ip if self.ws_server is not None else "",
                },
            }

            if should_update_api:
                try:
                    requests.post(
                        api_url + "/workers/update",
                        json=worker_data,
                        headers={"Authorization": f"Bearer {token}"},
                    )
                except Exception as e:
                    self.ctx.log(f"Failed to worker update status api: {e}")

                self.ctx.log("Updated worker status api")

    def update_current_step_name(self, step_name):
        self.current_step_name = step_name
        if self.current_step_callback is not None:
            self.current_step_callback(step_name)

        asyncio.create_task(self.update_website())

    def update_proc_done(self, proc_done):
        self.proc_done = proc_done
        if self.proc_done_callback is not None:
            self.proc_done_callback(proc_done)

        # update max every minute the proc done
        asyncio.create_task(self.update_website())

    async def constant_updates(self):
        if (
            os.environ.get("status_update_api_url", "") == ""
            or os.environ.get("ws_update", "false") == "false"
        ):
            return

        tqdm.write("Starting constant updates")
        self.ws_server = WebsocketServer()
        self.ws_server.run()
        while True:
            worker_data = {
                "type": "worker",
                "data": {
                    "id": (socket.gethostname()),
                    "status": f"Working on {self.ctx.title}",
                    "utilization": int(psutil.cpu_percent()),
                    "ws_ip": self.ws_server.ip if self.ws_server is not None else "",
                },
            }
            status_data = {
                "type": "status",
                "data": {
                    "img": self.ctx.poster_url,
                    "status": round(self.proc_done, 1),  # rounded
                    "title": self.ctx.title,
                    "phase": self.current_step_name,
                },
            }

            await self.ws_server.publish(json.dumps(worker_data), type="worker")
            await self.ws_server.publish(json.dumps(status_data), type="status")
            await asyncio.sleep(0.5)

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

        def encode_finished():
            if self.ctx.multi_res_pipeline:
                return os.path.exists(self.ctx.output_file)
                # TODO: do a paranoid check for all files
            else:
                return os.path.exists(self.ctx.output_file)

        if not encode_finished():
            constant_updates = asyncio.create_task(self.constant_updates())
            self.update_current_step_name("Running scene detection")
            sequence: ChunkSequence = get_video_scene_list_skinny(
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

            self.update_proc_done(10)
            self.update_current_step_name("Analyzing content")
            await run_sequence_pipeline(self.ctx, sequence)
            chunks_sequence = sequence

            self.update_proc_done(20)
            self.update_current_step_name("Encoding scenes")

            iter_counter = 0
            if self.ctx.dry_run:
                iter_counter = 2

            while chunks_sequence.sequence_integrity_check():
                iter_counter += 1
                if iter_counter > 3:
                    print("Integrity check failed 3 times, aborting")
                    quit()

                try:
                    command_objects = []
                    ctx = self.ctx
                    frames_encoded_so_far = 0
                    size_kb_so_far = 0

                    def is_done(c):
                        if ctx.multi_res_pipeline:
                            enc = ctx.get_encoder()
                            vmafs = get_vmaf_list(enc.get_codec())

                            for vmaf in vmafs:
                                output_path = (
                                    f"{ctx.temp_folder}/"
                                    f"{c.chunk_index}_{vmaf}.{enc.get_chunk_file_extension()}"
                                )
                                if not os.path.exists(output_path):
                                    return False

                            return True
                        else:
                            return c.is_done()

                    for chunk in sequence.chunks:
                        if not is_done(chunk):
                            command_objects.append(ChunkEncoder(ctx, chunk))
                        else:
                            frames_encoded_so_far += chunk.get_frame_count()
                            size_kb_so_far += chunk.size_kB

                    threads = os.cpu_count()
                    if len(command_objects) < threads:
                        ctx.prototype_encoder.threads = int(
                            threads / len(command_objects)
                        )

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

                    print(
                        f"Starting encoding of {len(command_objects)} out of {len(sequence.chunks)} scenes"
                    )

                    already_done = len(sequence.chunks) - len(command_objects)

                    def update_proc_done(num_finished_scenes):
                        # map 20 to 95% as the space where the scenes are encoded
                        self.update_proc_done(
                            20
                            + (already_done + num_finished_scenes)
                            / len(sequence.chunks)
                            * 75
                        )

                    if len(command_objects) == 0:
                        print("Nothing to encode, skipping")
                    else:
                        encode_task = asyncio.create_task(
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
                            )
                        )
                        await encode_task

                    refine_steps = get_refine_steps(ctx)
                    for step in refine_steps:
                        step(ctx, sequence)

                except KeyboardInterrupt:
                    print("Keyboard interrupt, stopping")
                    # kill all async tasks
                    for task in asyncio.all_tasks():
                        task.cancel()
                    quit()

            if not self.ctx.multi_res_pipeline:
                self.update_proc_done(95)
                self.update_current_step_name("Concatenating scenes")

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
            constant_updates.cancel()
        else:
            print("Output file exists 🤑, printing stats")

        self.update_proc_done(99)
        self.update_current_step_name("Final touches")

        print_stats(
            output_folder=self.ctx.output_folder,
            output=self.ctx.output_file,
            input_file=self.ctx.raw_input_file,
            grain_synth=self.ctx.prototype_encoder.grain_synth,
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

        self.update_proc_done(100)
        self.update_current_step_name("Done")
        if self.finished_callback is not None:
            self.finished_callback()

        self.delete()
