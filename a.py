import glob
import json
import os
import time

from hoeEncode.CeleryAutoscaler import Load

if __name__ == '__main__':
    dir = '/home/kokoniara/dev/VideoSplit/love_death_e4/stats'
    objects = []
    # load all json files in dir
    for file in glob.glob(os.path.join(dir, '*.json')):
        # load
        objects.append(json.load(open(file, 'r')))

    # print(objects)
    for obj in objects:
        if obj['bitrate'] >= 3000:
            print(f'over 3000 {obj["chunk_index"]}')

    quit()

    load = Load()

    # sleep and do 5 loops
    for i in range(5):
        cpu_load = load.get_load()
        print(cpu_load)
        mem_usage = load.get_free_mem()
        print(mem_usage)
        max_cpu_scenes = max(1, int((1 - cpu_load) * 500))
        max_mem_scenes = max(1, int(mem_usage * 500))

        scenes_to_encode = min(max_cpu_scenes, max_mem_scenes)
        print('scenes_to_encode', scenes_to_encode)
        time.sleep(1)
