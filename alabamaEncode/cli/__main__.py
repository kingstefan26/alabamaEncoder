#!/usr/bin/python
import asyncio
import atexit
import os
import sys
import time

from alabamaEncode.cli.cli_setup.autopaths import auto_output_paths
from alabamaEncode.cli.cli_setup.cli_args import read_args
from alabamaEncode.cli.cli_setup.paths import parse_paths
from alabamaEncode.cli.cli_setup.ratecontrol import parse_rd
from alabamaEncode.cli.cli_setup.res_preset import parse_resolution_presets
from alabamaEncode.cli.cli_setup.validate_files import validate_input
from alabamaEncode.cli.cli_setup.video_filters import parse_video_filters
from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.core.extras.auto_thumbnailer import AutoThumbnailer
from alabamaEncode.core.job import AlabamaEncodingJob
from alabamaEncode.parallel_execution.celery_app import app
from alabamaEncode.parallel_execution.worker import worker

runtime = -1
runtime_file = ""
lock_file_path = ""


def run_pipeline(ctx):
    creation_pipeline = [
        auto_output_paths,
        parse_paths,
        validate_input,
        parse_rd,
        parse_resolution_presets,
        parse_video_filters,
    ]
    for pipeline_item in creation_pipeline:
        ctx = pipeline_item(ctx)
    return ctx


def fmt_time(seconds) -> str:
    # Convert seconds to hours and remaining seconds
    hours, remainder = divmod(seconds, 3600)

    # If at least one hour has passed
    if hours:
        return f"{int(hours)} hour(s) {int(remainder)} second(s)"
    else:
        return f"{int(seconds)} second(s)"


@atexit.register
def at_exit():
    global runtime
    global runtime_file
    if runtime != -1:
        current_session_runtime = time.time() - runtime

        saved_runtime = 0
        if os.path.exists(runtime_file):
            with open(runtime_file) as f:
                saved_runtime = float(f.read())
        print(
            f"Current Session Runtime: {fmt_time(current_session_runtime)},"
            f" Runtime From Previous Sessions: {fmt_time(saved_runtime)},"
            f" Total Runtime: {fmt_time(current_session_runtime + saved_runtime)}"
        )

        try:
            with open(runtime_file, "w") as f:
                f.write(str(current_session_runtime + saved_runtime))
        except FileNotFoundError:
            pass
        if os.path.exists(lock_file_path):
            os.remove(lock_file_path)


def main():
    """
    Main entry point
    """
    if os.name == "nt":
        print("Windows is not supported")
        quit()

    global runtime
    runtime = time.time()

    ctx: AlabamaContext = AlabamaContext()

    ctx, args = read_args(ctx)

    match args.command:
        case "clear":
            print("Clearing celery queue")
            app.control.purge()
            quit()
        case "worker":
            worker(args.workers)
        case "autothumbnailer":
            if not os.path.exists(args.input):
                print(f"File {args.input} does not exist")
                quit()

            thumbnailer = AutoThumbnailer()
            thumbnailer.calc_face = args.detect_faces
            thumbnailer.generate_previews(
                input_file=args.input, output_folder=os.path.dirname(args.input)
            )
            quit()

    ctx = run_pipeline(ctx)

    global runtime_file
    global lock_file_path
    runtime_file = os.path.join(ctx.temp_folder, "runtime.txt")
    lock_file_path = os.path.join(ctx.output_folder, "alabama.lock")

    if os.path.exists(lock_file_path):
        print(
            "Lock file exists, are you sure another instance is not encoding in this folder? "
            "if not delete the lock file and try again"
        )
        quit()
    else:
        open(lock_file_path, "w").close()

    output_lock = os.path.join(ctx.temp_folder, "output.lock")
    if not os.path.exists(output_lock):
        with open(output_lock, "w") as f:
            f.write(ctx.raw_input_file)
    else:
        output_file_from_lock = open(output_lock).read()
        if output_file_from_lock != ctx.raw_input_file:
            print(
                f"Output file from lock file {output_file_from_lock} does not match output file "
                f"from ctx {ctx.raw_input_file}"
            )
            quit()

    if ctx.offload_server != "":
        print("Offloading to remote server")
        auth_token = os.environ.get("AUTH_BEARER_TOKEN", "")
        if auth_token == "":
            print("No AUTH_BEARER_TOKEN set, exiting")
            sys.exit(1)
        import requests
        import json

        headers = {"Authorization": f"Bearer {auth_token}"}
        data = json.dumps(ctx.to_json())
        requests.post(f"{ctx.offload_server}/jobs", data=data, headers=headers)

    job = AlabamaEncodingJob(ctx)

    asyncio.run(job.run_pipeline())  # this runs the whole encoding process

    quit()


if __name__ == "__main__":
    main()
