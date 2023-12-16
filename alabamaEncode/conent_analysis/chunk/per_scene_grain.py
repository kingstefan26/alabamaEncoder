from alabamaEncode.conent_analysis.chunk_analyse_pipeline_item import (
    ChunkAnalyzePipelineItem,
)
from alabamaEncode.core.alabama import AlabamaContext
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.scene.chunk import ChunkObject


class GrainSynth(ChunkAnalyzePipelineItem):
    def run(self, ctx: AlabamaContext, chunk: ChunkObject, enc: Encoder) -> Encoder:
        from alabamaEncode.adaptive.helpers.grain2 import calc_grainsynth_of_scene

        from alabamaEncode.adaptive.helpers.probe_file_path import get_probe_file_base

        probe_file_base = get_probe_file_base(chunk.chunk_path)
        grain_synth_result = calc_grainsynth_of_scene(
            chunk, probe_file_base, scale_vf=ctx.scale_string, crop_vf=ctx.crop_string
        )
        grain_synth_result = min(grain_synth_result, 18)
        enc.grain_synth = grain_synth_result

        grain_log = f"{ctx.temp_folder}grain.log"
        with open(grain_log, "a") as f:
            f.write(f"{chunk.log_prefix()}computed gs {enc.grain_synth}\n")
        return enc
