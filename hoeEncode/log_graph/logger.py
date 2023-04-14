import json


class ChunkLog:
    # wanted
    # bitrate: 500.0
    # k
    # bitrate
    # using
    # crf
    # 16: 8339
    # k
    # ssim: 0.98844
    # complexity: 0
    # complexity = (((bitrate / 1000000) / ssim) - 1) / 2
    # theoredical
    # ABR
    # rate = (target * complexity) + target = 500.0
    # k
    encode_time = 0
    rate_search_time = 0
    grain_search_time = 0

    ideal_grain = 0
    ideal_rate = 0

    final_vmaf = 0
    final_size = 0

    probe_ssim = 0
    probe_bitrate = 0
    wanted_rate = 0
    complexity = 0
    bitrate = 0

class ChunkLogger:
    chunks = []

    def log(self, chunk_index, **kwargs):
        if self.chunks[chunk_index] is None:
            self.chunks[chunk_index] = ChunkLog()
        self.chunks[chunk_index].update(kwargs)

    def dump(self, filename):
        json.dump(self.chunks, open(filename, "w"))