"""
Class that decides the best: grain, some encoding parameters, average bitrate for a video file
In comparison to Adaptive command, this should only be run once per video. Adaptive command is run per chunk.
"""
import os.path
import pickle

from hoeEncode.adaptiveEncoding.sub.bitrateLadder import AutoBitrateLadder
from hoeEncode.adaptiveEncoding.sub.grain import get_best_avg_grainsynth
from hoeEncode.adaptiveEncoding.sub.param import AutoParam
from hoeEncode.encoders import EncoderConfig
from hoeEncode.sceneSplit.Chunks import ChunkSequence


def do_adaptive_analasys(chunk_sequence: ChunkSequence, config: EncoderConfig, do_grain=True, do_bitrate_ladder=True,
                         do_qm=True):
    print('Starting adaptive content analysis')
    os.makedirs(f'{config.temp_folder}/adapt/', exist_ok=True)
    
    if os.path.exists(f'{config.temp_folder}/adapt/configCache.pt'):
        try:
            config = pickle.load(open(f'{config.temp_folder}/adapt/configCache.pt', 'rb'))
        except:
            pass
    else:
        if do_bitrate_ladder:
            ab = AutoBitrateLadder(chunk_sequence, config)

            config.bitrate = ab.get_best_bitrate()

        if do_grain:
            config.grain_synth = get_best_avg_grainsynth(input_file=chunk_sequence.input_file,
                                                         scenes=chunk_sequence,
                                                         temp_folder=config.temp_folder,
                                                         cache_filename=config.temp_folder + '/adapt/ideal_grain.pt',
                                                         bitrate=config.bitrate,
                                                         scene_pick_seed=2)

        if do_qm:
            ab = AutoParam(chunk_sequence, config)

            best_qm = ab.get_best_qm()

            config.qm_enabled = best_qm['qm']
            config.qm_min = best_qm['qm_min']
            config.qm_max = best_qm['qm_max']

        if config.grain_synth > 8 and config.bitrate < 1400:
            print('Turning off grain denoise because bitrate is too low')
            config.film_grain_denoise = 0

        pickle.dump(config, open(f'{config.temp_folder}/adapt/configCache.pt', 'wb'))

    return config
