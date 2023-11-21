#!/usr/bin/python
import atexit
import os
import pickle
import sys
import time

from alabamaEncode.core.alabama import AlabamaContext, setup_context
from alabamaEncode.core.execute_context import run
from alabamaEncode.parallelEncoding.CeleryApp import app
from alabamaEncode.parallelEncoding.worker import worker

runtime = -1
runtime_file = ""
lock_file_path = ""


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
            f"Current Session Runtime: {current_session_runtime}, Runtime From Previous Sessions: {saved_runtime},"
            f" Total Runtime: {current_session_runtime + saved_runtime}"
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
                # unpickle ctx from the file "alabamaResume", if doesnt exist in current dir quit
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

    global runtime_file
    global lock_file_path
    runtime_file = ctx.temp_folder + "runtime.txt"
    lock_file_path = ctx.output_folder + "lock"

    if os.path.exists(lock_file_path):
        print(
            "Lock file exists, are you sure another instance is not using encoding in this folder? "
            "if not delete the lock file and try again"
        )
        quit()
    else:
        open(lock_file_path, "w").close()

    output_lock = ctx.temp_folder + "output.lock"
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

    run(ctx)

    quit()


if __name__ == "__main__":
    main()
