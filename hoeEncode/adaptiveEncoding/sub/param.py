import copy
import os
import random
from concurrent.futures import ThreadPoolExecutor

from hoeEncode.encoders.EncoderConfig import EncoderConfigObject
from hoeEncode.encoders.EncoderJob import EncoderJob
from hoeEncode.encoders.RateDiss import RateDistribution
from hoeEncode.encoders.encoderImpl.Svtenc import AbstractEncoderSvtenc
from hoeEncode.ffmpegUtil import get_video_vmeth
from hoeEncode.sceneSplit.Chunks import ChunkSequence


class AutoParam:
    def __init__(self, chunks: ChunkSequence, config: EncoderConfigObject):
        self.chunks = chunks
        self.config = config

    def get_bd(
        self, chunk: EncoderJob, qm_enabled, min, max, runs, probe_name, probe_folder
    ):
        svt = AbstractEncoderSvtenc()
        svt.eat_job_config(EncoderJob(chunk=chunk), self.config)
        svt.update(
            passes=1, crf=16, rate_distribution=RateDistribution.CQ, threads=3, speed=5
        )
        chunk.chunk_path = probe_folder + probe_name
        svt.update(output_path=chunk.chunk_path)
        svt.qm_enabled = qm_enabled
        svt.qm_min = min
        svt.qm_max = max
        svt.run()
        db_rate = (os.path.getsize(chunk.chunk_path) / 1000) / get_video_vmeth(
            chunk.chunk_path, chunk, crop_string=self.config.crop_string
        )
        print(f"{probe_name} -> {db_rate} DB rate")
        runs.append(
            (
                db_rate,
                {
                    "qm": qm_enabled,
                    "qm_min": min,
                    "qm_max": max,
                },
            )
        )

    def get_best_qm(self) -> dict[str, int]:
        print("Starting autoParam best qm test")
        probe_folder = f"{self.config.temp_folder}/adapt/qm/"
        os.makedirs(probe_folder, exist_ok=True)

        # random chunk that is not in the first 20% or last 20% of the video
        tst_chunk = copy.deepcopy(
            random.choice(
                self.chunks.chunks[
                    int(len(self.chunks.chunks) * 0.2) : int(
                        len(self.chunks.chunks) * 0.8
                    )
                ]
            )
        )
        tst_chunk.chunk_index = 0
        runs = []

        with ThreadPoolExecutor(max_workers=4) as executor:
            executor.submit(
                self.get_bd,
                copy.deepcopy(tst_chunk),
                False,
                0,
                0,
                runs,
                "no_qm.ivf",
                probe_folder,
            )
            executor.submit(
                self.get_bd,
                copy.deepcopy(tst_chunk),
                True,
                0,
                15,
                runs,
                "0_15.ivf",
                probe_folder,
            )
            executor.submit(
                self.get_bd,
                copy.deepcopy(tst_chunk),
                True,
                8,
                15,
                runs,
                "8_15.ivf",
                probe_folder,
            )
            executor.submit(
                self.get_bd,
                copy.deepcopy(tst_chunk),
                True,
                0,
                8,
                runs,
                "0_8.ivf",
                probe_folder,
            )
            executor.shutdown()

        # get the one with the lowest db rate and return it
        runs.sort(key=lambda x: x[0])
        print(f"Best qm -> {runs[0][1]}")
        return runs[0][1]
