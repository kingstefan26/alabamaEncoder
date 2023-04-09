from hoeEncode.ConvexHullEncoding.AutoGrain import get_best_avg_grainsynth
from hoeEncode.split.split import get_video_scene_list

if __name__ == '__main__':
    # set up logging
    import logging

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    input_file = '/mnt/sda1/shows/The Chilling Adventures of Sabrina/Season 1/[TorrentCouch.net].The.Chilling.Adventures.Of.Sabrina.S01E03.720p.WEBRip.x264.mp4'

    scene_list = get_video_scene_list(input_file, 'scenecache.json')

    # avg test
    get_best_avg_grainsynth(scenes=scene_list, input_file=input_file, random_pick=3)
