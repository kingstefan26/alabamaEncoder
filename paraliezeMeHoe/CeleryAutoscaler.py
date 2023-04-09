import multiprocessing
import os
import re

from celery.worker.autoscale import Autoscaler as CeleryAutoscaler


# https://gist.github.com/hussainfolio3/c5246f59f9e5c31fa720524fb45b2077
# never go above one worker = one core
# if we have 12 cores then max is 12 workers

class DAAutoscaler(CeleryAutoscaler):
    # Try to keep the load above this point.
    LOAD_MIN = .8
    # Try to keep the load below this.
    LOAD_MAX = 1.1
    # We need this percentage of free memory to scale up.
    MEM_FREE_SCALE_UP = .3
    # Any less than this memory and we scale down.
    MEM_FREE_SCALE_DOWN = .2

    def __init__(self, *args, **kwargs):
        self.num_cpus = multiprocessing.cpu_count()
        print(f"DAAutoscaler: Num CPUs {self.num_cpus}")
        super(DAAutoscaler, self).__init__(*args, **kwargs)

    def _maybe_scale(self, req=None):
        """Scale up or down if we too much/little load or memory."""
        cur_load = self._get_load()
        mem_free = self._get_free_mem()
        if cur_load < self.LOAD_MIN and mem_free > self.MEM_FREE_SCALE_UP:
            mul = int(self.LOAD_MAX / cur_load)
            print(f"DAAutoscaler: Scale Up {mul}X {cur_load} free={100 * mem_free}%")
            self.scale_up(1)
            return True
        if cur_load > self.LOAD_MAX or mem_free < self.MEM_FREE_SCALE_DOWN:
            mul = int(cur_load / self.LOAD_MAX)
            print(f"DAAutoscaler: Scale Down {mul}X {cur_load} free={100 * mem_free}%")
            self.scale_down(mul)
            return True
        print(f"DAAutoscaler: Ok {cur_load} {100 * mem_free}%")

    def _get_load(self):
        load1min, load5min, load15min = os.getloadavg()
        # Prevent divide by zero
        if load1min < 0.001:
            load1min = 0.001
        return 1.0 * load1min / self.num_cpus

    re_total = re.compile(r"MemTotal:\s+(?P<total>\d+)\s+kB")
    re_free = re.compile(r"MemFree:\s+(?P<free>\d+)\s+kB")

    def _get_free_mem(self):
        """Return percentage of free memory 0.0 to 1.0."""
        try:
            # Try using the cross-platform method.
            import psutil
        except ImportError:
            # If not, make it work for most linux distros.
            with open('/proc/meminfo', 'rb') as f:
                mem = f.read()
            return (1.0 * int(self.re_free.search(mem).group("free")) /
                    int(self.re_total.search(mem).group("total")))
        else:
            return psutil.virtual_memory().percent / 100
