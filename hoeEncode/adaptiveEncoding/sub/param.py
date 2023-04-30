import copy
import os
import random

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

    def get_best_qm(self) -> dict[str, int]:
        print('Starting autoParam best qm test')
        probe_folder = f'{self.config.temp_folder}/adapt/qm/'
        os.makedirs(probe_folder, exist_ok=True)

        # random chunk that is not in the first 20% or last 20% of the video
        tst_chunk = copy.deepcopy(
            random.choice(self.chunks.chunks[int(len(self.chunks.chunks) * 0.2):int(len(self.chunks.chunks) * 0.8)])
        )
        tst_chunk.chunk_index = 0
        svt = AbstractEncoderSvtenc()
        svt.eat_job_config(EncoderJob(chunk=tst_chunk), self.config)
        svt.update(passes=1, crf=16, rate_distribution=RateDistribution.CQ, threads=os.cpu_count(), speed=5)

        runs = []

        tst_chunk.chunk_path = probe_folder + 'no_qm.ivf'
        svt.update(output_path=tst_chunk.chunk_path)
        svt.qm_enabled = False
        svt.run()
        no_qm_bd = (os.path.getsize(tst_chunk.chunk_path) / 1000) \
                   / get_video_vmeth(tst_chunk.chunk_path, tst_chunk, crop_string=self.config.crop_string)
        print(f'No qm -> {no_qm_bd} DB rate')
        runs.append((no_qm_bd, {
            'qm': False,
            'qm_min': 0,
            'qm_max': 0,
        }))

        tst_chunk.chunk_path = probe_folder + '0_15.ivf'
        svt.update(output_path=tst_chunk.chunk_path)
        svt.qm_enabled = True
        svt.qm_min = 0
        svt.qm_max = 15
        svt.run()
        qm_0_15_bd = (os.path.getsize(tst_chunk.chunk_path) / 1000) \
                     / get_video_vmeth(tst_chunk.chunk_path, tst_chunk, crop_string=self.config.crop_string)
        print(f'0-15 qm -> {qm_0_15_bd} DB rate')
        runs.append((qm_0_15_bd, {
            'qm': True,
            'qm_min': 0,
            'qm_max': 15,
        }))

        tst_chunk.chunk_path = probe_folder + '8_15.ivf'
        svt.update(output_path=tst_chunk.chunk_path)
        svt.qm_enabled = True
        svt.qm_min = 8
        svt.qm_max = 15
        svt.run()
        qm_8_15_bd = (os.path.getsize(tst_chunk.chunk_path) / 1000) \
                     / get_video_vmeth(tst_chunk.chunk_path, tst_chunk, crop_string=self.config.crop_string)
        print(f'8-15 qm -> {qm_8_15_bd} DB rate')
        runs.append((qm_8_15_bd, {
            'qm': True,
            'qm_min': 8,
            'qm_max': 15,
        }))

        tst_chunk.chunk_path = probe_folder + '0_8.ivf'
        svt.update(output_path=tst_chunk.chunk_path)
        svt.qm_enabled = True
        svt.qm_min = 0
        svt.qm_max = 8
        svt.run()
        qm_0_8_bd = (os.path.getsize(tst_chunk.chunk_path) / 1000) \
                    / get_video_vmeth(tst_chunk.chunk_path, tst_chunk, crop_string=self.config.crop_string)
        print(f'0-8 qm -> {qm_0_8_bd} DB rate')
        runs.append((qm_0_8_bd, {
            'qm': True,
            'qm_min': 0,
            'qm_max': 8,
        }))

        # get the one with the lowest db rate and return it
        runs.sort(key=lambda x: x[0])
        return runs[0][1]
