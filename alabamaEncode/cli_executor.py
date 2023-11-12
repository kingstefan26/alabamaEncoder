import os
import subprocess
from typing import List


class CliResult:
    def __init__(self, return_code, output):
        self.return_code = return_code
        self.output = output

    def __repr__(self):
        return f"ExecuteResult(return_code={self.return_code}, output={self.output})"

    def __str__(self):
        return self.output()

    def success(self) -> bool:
        return self.return_code == 0

    def get_output(self) -> str:
        return self.output

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
        :param files: list of files that must exist
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
                if not os.path.exists(file):
                    raise RuntimeError(fail_message)
        return self

    def get_as_int(self) -> int:
        return int(self.output.strip())

    def filter_output(self, filter: str):
        self.output = self.output.strip().replace(filter, "")
        return self

    def get_as_float(self) -> float:
        return float(self.output.strip())


def run_cli(cmd, timeout_value=-1) -> CliResult:
    p = subprocess.Popen(
        cmd,
        shell=True,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    if timeout_value > 0:
        p.wait(timeout=timeout_value)
    else:
        p.wait()

    output = p.stdout.read()

    return CliResult(p.returncode, output.decode("utf8"))
