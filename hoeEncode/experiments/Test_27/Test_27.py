from hoeEncode.adaptiveEncoding.sub.grain import get_best_avg_grainsynth

if __name__ == '__main__':
    print("Test 27: AutoGrainSynth")

    input_file = '/mnt/sda1/shows/The Chilling Adventures of Sabrina/Season 1/[TorrentCouch.net].The.Chilling.Adventures.Of.Sabrina.S01E03.720p.WEBRip.x264.mp4'

    scene_list = None

    # avg test
    grain = get_best_avg_grainsynth(scenes=scene_list, input_file=input_file)
    print('result: ' + str(grain))
