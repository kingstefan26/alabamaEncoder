from typing import List

from hoeEncode.encoders.EncoderConfig import EncoderConfigObject
from hoeEncode.encoders.EncoderJob import EncoderJob
from hoeEncode.encoders.encoderImpl.Svtenc import AbstractEncoderSvtenc
from hoeEncode.sceneSplit.ChunkOffset import ChunkObject


class AutoParamClass:

    def get_best_qm(self, chunk: ChunkObject, config: EncoderConfigObject) -> dict[str, int]:
        '''

        :param chunk:
        :param config:
        :return: enabled 0|1, min 0-15, max 0-15
        '''
        svt = AbstractEncoderSvtenc()
        svt.eat_job_config(EncoderJob(chunk=chunk, current_scene_index=0, encoded_scene_path='./qmtest{a}'), config)
        return {
            'qm': 0,
            'min': 0,
            'max': 0,
        }
