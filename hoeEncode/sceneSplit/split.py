import json
import os
from typing import List

from scenedetect import detect, AdaptiveDetector

from hoeEncode.ffmpegUtil import get_frame_count
from hoeEncode.sceneSplit.ChunkOffset import ChunkObject
from hoeEncode.sceneSplit.Chunks import ChunkSequence


def get_video_scene_list(file_path: str, scene_cache_file_name: str, skip_check: bool = False) -> List[List[int]]:
    if os.path.exists(scene_cache_file_name):
        print('Found SceneCache... loading')
        scenes = json.load(open(scene_cache_file_name, ))
        if not skip_check:
            video_lenght = get_frame_count(file_path)
            # add up all scenes in scenes
            sum = 0
            for i in scenes:
                sum += i[1] - i[0]

            # if the sum is not equal to the video lenght, then the video has changed
            if sum != video_lenght:
                cache = f'Video ({file_path}) does not match scene cache ({scene_cache_file_name}), please delete the scene cache'
                raise Exception(cache)
        print(f"Found {len(scenes)} scenes")
        return scenes
    else:
        print('Creating SceneCache')
        scenes = []
        scene_list = detect(video_path=file_path, detector=AdaptiveDetector(), show_progress=True)
        for index, scene in enumerate(scene_list):
            scenes.append([scene[0].get_frames(), scene[1].get_frames()])
        print("Saving scene cache to " + scene_cache_file_name)
        with open(scene_cache_file_name, 'w') as cache_file:
            cache_file.write(json.dumps(scenes))
        print(f"Found {len(scenes)} scenes")
        return scenes


def get_video_scene_list_skinny(file_path: str, scene_cache_file_name: str, skip_check: bool = False) -> ChunkSequence:
    if os.path.exists(scene_cache_file_name):
        print('Found SceneCache... loading')
        scenes = json.load(open(scene_cache_file_name, ))
        if not skip_check:
            video_lenght = get_frame_count(file_path)
            # add up all scenes in scenes
            sum = 0
            for i in scenes:
                sum += i[1] - i[0]

            # if the sum is not equal to the video lenght, then the video has changed
            if sum != video_lenght:
                cache = f'Video ({file_path}) does not match scene cache ({scene_cache_file_name}), please delete the scene cache'
                raise Exception(cache)
        print(f"Found {len(scenes)} scenes")
    else:
        print('Creating SceneCache')
        scenes = []
        scene_list = detect(video_path=file_path, detector=AdaptiveDetector(), show_progress=True)
        for index, scene in enumerate(scene_list):
            scenes.append([scene[0].get_frames(), scene[1].get_frames()])
        print("Saving scene cache to " + scene_cache_file_name)
        with open(scene_cache_file_name, 'w') as cache_file:
            cache_file.write(json.dumps(scenes))
        print(f"Found {len(scenes)} scenes")

    return ChunkSequence([ChunkObject(path=file_path, first_frame_index=i[0], last_frame_index=i[1]) for i in scenes])
