import multiprocessing
import os
import re

from celery.worker.autoscale import Autoscaler as CeleryAutoscaler

from alabamaEncode.core.util.cli_executor import run_cli


# https://gist.github.com/hussainfolio3/c5246f59f9e5c31fa720524fb45b2077
# never go above one worker = one core
# if we have 12 cores then max is 12 workers


def parse_swap_usage() -> float:
    """
    Parse the output of 'swapon -s' and return the swap usage in percent.
    :return:
    """
    # Execute the 'swapon -s' and get the output
    output = run_cli("swapon -s").get_output()

    # Split the output into lines
    lines = output.split("\n")[1:]  # We skip the header

    for line in lines:
        if line:  # Ignore empty lines
            parts = line.split()

            # We assume that the line structure is correct here,
            # i.e., there are at least 5 parts.
            filename, type_, size, used, priority = (
                parts[0],
                parts[1],
                parts[2],
                parts[3],
                parts[4],
            )

            # Calculate and print usage Proportion
            usage = int(used) / int(size)
            # print(f"Swap usage for {filename}: {usage * 100:.2f}%")
            return usage * 100


class Load:
    def __init__(self):
        self.num_cpus = multiprocessing.cpu_count()

    def get_load(self):
        """Get cpu load in %"""
        load1min, load5min, load15min = os.getloadavg()
        # Prevent divide by zero
        if load1min < 0.001:
            load1min = 0.001
        return 1.0 * load1min / self.num_cpus

    re_total = re.compile(r"MemTotal:\s+(?P<total>\d+)\s+kB")
    re_free = re.compile(r"MemFree:\s+(?P<free>\d+)\s+kB")

    def get_free_mem(self):
        """Return percentage of free memory 0.0 to 1.0."""
        # If not, make it work for most linux distros.
        with open("/proc/meminfo", "rb") as f:
            mem = f.read().decode("utf-8")
            return (
                1.0
                * int(self.re_free.search(mem).group("free"))
                / int(self.re_total.search(mem).group("total"))
            )


# Load tests
if __name__ == "__main__":
    load = Load()
    print(f"Load: {load.get_load()}")
    print(f"Free mem: {load.get_free_mem()}")
    print(f"Swap usage: {parse_swap_usage()}%")


class DAAutoscaler(CeleryAutoscaler):
    # Try to keep the load above this point.
    LOAD_MIN = 0.8
    # Try to keep the load below this.
    LOAD_MAX = 1.1
    # We need this percentage of free memory to scale up.
    MEM_FREE_SCALE_UP = 0.3
    # Any less than this memory and we scale down.
    MEM_FREE_SCALE_DOWN = 0.1

    MAX_SCALE_UP = 5
    MIN_SCALE_DOWN = 1

    def __init__(self, *args, **kwargs):
        self.load = Load()
        print(f"DAAutoscaler: Num CPUs {self.load.num_cpus}")
        super(DAAutoscaler, self).__init__(*args, **kwargs)

    def _maybe_scale(self, req=None):
        """Scale up or down if we too much/little load or memory."""
        cur_load = self.load.get_load()
        mem_free = self.load.get_free_mem()

        if cur_load < self.LOAD_MIN and mem_free > self.MEM_FREE_SCALE_UP:
            mul = int(self.LOAD_MAX / cur_load)
            mul = max(min(mul, self.MAX_SCALE_UP), self.MIN_SCALE_DOWN)
            print(
                f"DAAutoscaler: Scale Up {mul}X {round(cur_load, 2)} free={round(100 * mem_free, 2)}%"
            )
            self.scale_up(mul)
            return True
        if cur_load > self.LOAD_MAX or mem_free < self.MEM_FREE_SCALE_DOWN:
            mul = int(cur_load / self.LOAD_MAX)
            print(
                f"DAAutoscaler: Scale Down {mul}X {round(cur_load, 2)} free={round(100 * mem_free, 2)}%"
            )
            self.scale_down(mul)
            return True

        print(f"DAAutoscaler: Ok {cur_load} {100 * mem_free}%")
