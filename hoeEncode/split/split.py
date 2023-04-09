import json
import os
from typing import List

from scenedetect import detect, ContentDetector

from hoeEncode.encode.ffmpeg.FfmpegUtil import syscmd, get_frame_count


def mergeVideoFiles(listOfFilePaths, outputfile):
    with open('temp.txt', 'w') as f:
        for [_, _, path] in listOfFilePaths:
            path = path.replace('./', '')
            f.write("file '" + path + "'\n")
    syscmd('ffmpeg -v error -stats -f concat -safe 0 -i temp.txt -c copy ' + outputfile)
    os.remove('temp.txt')


def get_video_scene_list(file_path: str, scene_cache_file_name: str, skip_check: bool = False) -> List[List[int]]:
    if os.path.exists(scene_cache_file_name):
        print('Found SceneCache... loading')
        fragments = json.load(open(scene_cache_file_name, ))
        if not skip_check:
            video_lenght = get_frame_count(file_path)
            # add up all scenes in fragments
            sum = 0
            for i in fragments:
                sum += i[1] - i[0]

            # if the sum is not equal to the video lenght, then the video has changed
            if sum != video_lenght:
                raise Exception('Video does not match scene cache, please delete the scene cache')
        print(f"Found {len(fragments)} scenes")
        return fragments
    else:
        print('Creating SceneCache')
        fragments = []
        scene_list = detect(file_path, ContentDetector(), show_progress=True)
        for index, scene in enumerate(scene_list):
            # print('Scene %2d: Start %s / Frame %d, End %s / Frame %d' % (
            #     index + 1,
            #     scene[0].get_timecode(), scene[0].get_frames(),
            #     scene[1].get_timecode(), scene[1].get_frames(),))

            fragments.append([scene[0].get_frames(), scene[1].get_frames()])
        print("Saving scene cache to " + scene_cache_file_name)
        with open(scene_cache_file_name, 'w') as cache_file:
            cache_file.write(json.dumps(fragments))
        print(f"Found {len(fragments)} scenes")
        return fragments


if __name__ == "__main__":
    from hoeEncode.encode.ffmpeg.ChunkOffset import ChunkObject

    name = '/home/kokoniara/dev/VideoSplit/temp_mythicquests3e10/sceneCache.json'
    file = open(name, )
    fragemts = json.load(file)
    if not os.path.exists("./mergeTest/"):
        os.makedirs("./mergeTest/")
    imaslut = []
    for i, frag in enumerate(fragemts):
        tha_chunk = ChunkObject(path='/home/kokoniara/dev/VideoSplit/chunkThatIWantToEncde.mkv',
                                first_frame_index=frag[0],
                                last_frame_index=frag[1])
        test = f"ffmpeg -n -hwaccel vaapi -hwaccel_device /dev/dri/renderD128 -hwaccel_output_format vaapi {tha_chunk.get_ss_ffmpeg_command_pair()} -vf 'scale_vaapi=format=p010' -c:v hevc_vaapi -profile:v 2 -b:v 5M ./mergeTest/{i}.mkv"
        # print(test)
        syscmd(test)
        imaslut += [f"./mergeTest/{i}.mkv"]

    mergeVideoFiles(imaslut, "skinnylegend.mkv")
