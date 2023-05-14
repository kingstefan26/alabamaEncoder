"""
Testing/evaluating autoParam
"""

import os

from hoeEncode.adaptiveEncoding.sub.param import AutoParam
from hoeEncode.encoders.EncoderConfig import EncoderConfigObject
from hoeEncode.sceneSplit.Chunks import ChunkSequence
from hoeEncode.sceneSplit.split import get_video_scene_list_skinny

if __name__ == '__main__':
    test_folder = os.path.abspath('./tst/')
    input_file = "/home/kokoniara/dev/VideoSplit/temp_201/temp.mkv"
    config = EncoderConfigObject(vmaf=96,
                                 crop_string='crop=3808:1744:28:208,scale=-2:1080:flags=lanczos,zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=reinhard:desat=0,zscale=t=bt709:m=bt709:r=tv',
                                 temp_folder=test_folder,
                                 grain_synth=4)

    scenes_skinny: ChunkSequence = get_video_scene_list_skinny(input_file=input_file,
                                                               cache_file_path='/home/kokoniara/dev/VideoSplit/temp_201/sceneCache.pt',
                                                               max_scene_length=10)

    ab = AutoParam(scenes_skinny, config)

    best_qm = ab.get_best_qm()

    print(f'Best qm: {best_qm}')
