import time


class Timer:
    def __init__(self):
        self.timers = {}

    def start(self, name: str):
        self.timers[name] = time.time()

    def stop(self, name: str):
        if name not in self.timers:
            raise Exception("Timer not started")
        self.timers[name] = time.time() - self.timers[name]
        return self.timers[name]

    def finish(self, loud=False):
        if loud:
            print("timers:")
            for key in self.timers:
                print(f"{key}: {self.timers[key]}s")
        return self.timers
