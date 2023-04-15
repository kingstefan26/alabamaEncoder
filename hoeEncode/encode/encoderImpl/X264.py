from typing import List

from hoeEncode.encode.AbstractEncoder import AbstractEncoder
from hoeEncode.encode.encoderImpl.RateDiss import RateDistribution


class AbstractEncoderX264(AbstractEncoder):
    def get_encode_commands(self) -> List[str]:
        if self.chunk is None:
            raise Exception('FATAL: chunk is None')
        if self.temp_folder is None:
            raise Exception('FATAL: temp_folder is None')
        if self.current_scene_index is None:
            raise Exception('FATAL: current_scene_index is None')

        kommand = f'ffmpeg -y {self.chunk.get_ss_ffmpeg_command_pair()} -c:v libx264 {self.crop_string} -threads {self.threads} -g 999 -passlogfile {self.temp_folder}{self.current_scene_index}264 -pix_fmt yuv420p10le'

        match self.rate_distribution:
            case RateDistribution.VBR:
                kommand += f' -b:v {self.bitrate}k'
            case RateDistribution.CQ:
                kommand += f' -crf {self.crf}'
            case RateDistribution.CQ_VBV:
                if self.passes < 2:
                    raise Exception('FATAL: passes must be 2 or more for vbr')
                kommand += f' -crf {self.crf} -b:v {self.bitrate}k'
            case RateDistribution.VBR_VBV:
                if self.passes < 2:
                    raise Exception('FATAL: passes must be 2 or more for vbr vbv')
                kommand += f' -b:v {self.bitrate}k -maxrate {self.bitrate}k -bufsize -maxrate {int(self.bitrate * 2)}k'

        match self.speed:
            case 9:
                kommand += ' -preset ultrafast'
            case 8:
                kommand += ' -preset superfast'
            case 7:
                kommand += ' -preset veryfast'
            case 6:
                kommand += ' -preset faster'
            case 5:
                kommand += ' -preset fast'
            case 4:
                kommand += ' -preset medium'
            case 3:
                kommand += ' -preset slow'
            case 2:
                kommand += ' -preset slower'
            case 1:
                kommand += ' -preset veryslow'

        if self.passes == 2:
            c = [
                f'{kommand} -pass 1 -f null /dev/null',
                f'{kommand} -pass 2 {self.output_path}'
            ]
            print(c)
            return c
        elif self.passes == 1:
            return [
                f'{kommand} {self.output_path}'
            ]
