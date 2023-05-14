"""
Testing vbr auto bitrate vs crf auto bitrate
"""
import copy
import os
import random
from typing import List

from hoeEncode.adaptiveEncoding.sub.bitrateLadder import AutoBitrateLadder
from hoeEncode.encoders.EncoderConfig import EncoderConfigObject
from hoeEncode.sceneSplit.ChunkOffset import ChunkObject
from hoeEncode.sceneSplit.Chunks import ChunkSequence
from hoeEncode.sceneSplit.split import get_video_scene_list_skinny

if __name__ == '__main__':
    test_folder = os.path.abspath('./tst/')
    input_file = "/home/kokoniara/dev/VideoSplit/temp_201/temp.mkv"
    config = EncoderConfigObject(vmaf=96,
                                 crop_string='crop=3808:1744:28:208,scale=-2:1080:flags=lanczos,zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=reinhard:desat=0,zscale=t=bt709:m=bt709:r=tv',
                                 temp_folder=test_folder,
                                 grain_synth=4,
                                 bitrate=1560)
    config.crf_bitrate_mode = True

    scenes_skinny: ChunkSequence = get_video_scene_list_skinny(input_file=input_file,
                                                               cache_file_path='/home/kokoniara/dev/VideoSplit/temp_201/sceneCache.pt',
                                                               max_scene_length=10)

    ab = AutoBitrateLadder(scenes_skinny, config)

    chunks_copy: List[ChunkObject] = copy.deepcopy(scenes_skinny.chunks)
    chunks_copy = chunks_copy[int(len(chunks_copy) * 0.2):int(len(chunks_copy) * 0.8)]
    random.shuffle(chunks_copy)
    chunks = chunks_copy[:7]
    chunks: List[ChunkObject] = copy.deepcopy(chunks)

    # ab.get_best_bitrate(skip_cache=True)
    print(ab.get_target_crf(1560))
