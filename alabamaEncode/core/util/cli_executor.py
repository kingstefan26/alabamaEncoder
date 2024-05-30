import os
import re
import subprocess
import time
from queue import Queue
from threading import Thread
from typing import List, Callable, Optional

__all__ = ["run_cli", "run_cli_parallel", "CliResult"]


class CliResult:
    def __init__(self, return_code, output, time_taken=-1.0):
        self.return_code = return_code
        self.output = output
        self.time_taken = time_taken

    def __repr__(self):
        return f"ExecuteResult(return_code={self.return_code}, output={self.output})"

    def __str__(self):
        return self.output()

    def success(self) -> bool:
        return self.return_code == 0

    def get_output(self) -> str:
        return self.output

    def strip_mp4_warning(self):
        """
        sometimes when using ffprobe on mp4 files,
        [movmp4m4a3gp3g2mj2 @ 0x5579bcaa2fc0] Referenced QT chapter track not found\n
        appears in the output, this function removes it
        :return: self
        """
        self.output = re.sub(r"\[mov.+not found", "", self.output).strip()
        return self

    def verify(
        self,
        fail_message: str = "Cli failed",
        bad_output_hints: List[str] = None,
        files: List[str] = None,
    ):
        """
        :param fail_message: message to raise if the cli failed
        :param bad_output_hints: list of strings that,
        when found in the output, will cause the verification to fail
        :param files: a list of files that must exist and bigger than zero bytes
        :return: self for pipelining
        """
        if not self.success():
            raise RuntimeError(fail_message)
        if bad_output_hints:
            for hint in bad_output_hints:
                if hint in self.output and hint != "":
                    raise RuntimeError(fail_message)
                if hint == self.output:
                    raise RuntimeError(fail_message)
        if files:
            for file in files:
                if not os.path.exists(file) or os.path.getsize(file) == 0:
                    raise RuntimeError(fail_message)
        return self

    def get_as_int(self) -> int:
        return int(self.output.strip())

    def filter_output(self, filter_str: str):
        self.output = self.output.strip().replace(filter_str, "")
        return self

    def get_as_float(self) -> float:
        return float(self.output.strip())


def run_cli(
    cmd,
    timeout_value=-1,
    on_output: Optional[Callable[[str], None]] = None,
) -> CliResult:
    start = time.perf_counter()
    p = subprocess.Popen(
        cmd,
        shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    output = ""
    while p.poll() is None:  # While the process is still running...
        chunk = p.stdout.read(1).decode(errors="ignore")  # Read output chunk by chunk
        output += chunk  # Add chunk to total output
        if on_output is not None:  # If on_output is provided...
            on_output(chunk)  # ...apply it to each chunk

    if timeout_value > 0:
        try:
            p.wait(timeout=timeout_value)
        except subprocess.TimeoutExpired:
            p.kill()
    else:
        p.wait()

    output += p.stdout.read().decode(errors="ignore")

    end = time.perf_counter()
    return CliResult(p.returncode, output, end - start)


def _run_command(
    cmd: str, result_queue: Queue, stream_to_stdout: bool, error_flag: List[bool]
):
    process = subprocess.Popen(
        cmd,
        shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    # output = ""
    # for line in iter(lambda: process.stdout.read(1), b""):
    #     # if stream_to_stdout:
    #     # sys.stdout.write(line.decode("utf-8", errors="ignore"))
    #     # print(line.decode("utf-8", errors="ignore"), end="")
    #     output += str(line)

    output = process.stdout.read().decode(errors="ignore")

    process.wait()
    result_queue.put(CliResult(process.returncode, output))

    if process.returncode != 0:
        error_flag[0] = True


def run_cli_parallel(
    cmds: List[str], timeout_value=-1, stream_to_stdout=False
) -> List[CliResult]:
    results = []
    result_queue = Queue()
    error_flag = [False]

    threads = []
    for cmd in cmds:
        thread = Thread(
            target=_run_command, args=(cmd, result_queue, stream_to_stdout, error_flag)
        )
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join(timeout=timeout_value)

    # If any process finished with a non-zero code, terminate the remaining processes
    if any(error_flag):
        raise RuntimeError("One or more processes  finished with a non-zero exit code.")

    # Retrieve results from the queue
    while len(results) < len(cmds):
        out = result_queue.get()
        if out is not None:
            results.append(out)

    return results
