from hoeEncode.bitrateAdapt.AutoGrain import get_best_avg_grainsynth

if __name__ == '__main__':
    print("Test 27: AutoGrainSynth")
    # set up logging
    import logging

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    input_file = '/mnt/sda1/shows/The Chilling Adventures of Sabrina/Season 1/[TorrentCouch.net].The.Chilling.Adventures.Of.Sabrina.S01E03.720p.WEBRip.x264.mp4'

    scene_list = None

    # avg test
    grain = get_best_avg_grainsynth(scenes=scene_list, input_file=input_file, random_pick=3)
    print('result: ' + str(grain))
