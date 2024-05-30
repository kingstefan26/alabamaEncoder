import os

from alabamaEncode.conent_analysis.chunk.final_encode_step import FinalEncodeStep
from alabamaEncode.conent_analysis.opinionated_vmaf import get_vmaf_list
from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.encoder.encoder import Encoder
from alabamaEncode.encoder.stats import EncodeStats
from alabamaEncode.scene.chunk import ChunkObject


class EncodeMultiResFinals(FinalEncodeStep):
    def run(
        self, enc: Encoder, chunk: ChunkObject, ctx: AlabamaContext, encoded_a_frame
    ) -> EncodeStats:
        if ctx.get_kv().get("multires_final_paths", "final_paths") is None:
            return None
        # a = {
        #     "res": "720",
        #     "chunks": [
        #         {"chunk_index": "0", "crf": "11"},
        #         {"chunk_index": "1", "crf": "12"},
        #     ],
        # }
        #

        for vmaf in get_vmaf_list(enc.get_codec()):
            obj = ctx.get_kv().get("multires_trellis", str(vmaf))
            res = obj["res"] + ":-2"
            for c in obj["chunks"]:
                if c["chunk_index"] == chunk.chunk_index:
                    enc.crf = c["crf"]
                    break

            # set res
            vf = ctx.prototype_encoder.video_filters.split(",")
            scale_str = f"scale={res}:flags=lanczos"

            # replace the first scale filter if it exists
            for i in range(len(vf)):
                if ":flags=lanczos" in vf[i]:
                    vf[i] = scale_str
                    break

            # if there is no scale filter, add it to the end
            if scale_str not in ",".join(vf):
                vf.append(scale_str)

            vf = [f for f in vf if f != ""]

            enc.video_filters = ",".join(vf)

            enc.output_path = f"{ctx.temp_folder}{chunk.chunk_index}_{vmaf}{enc.get_chunk_file_extension()}"

            if not os.path.exists(enc.output_path):
                ctx.get_kv().set(
                    "multires_final_paths",
                    f"{chunk.chunk_index}_{vmaf}",
                    enc.output_path,
                )
                enc.run()

        return None

    def dry_run(self, enc: Encoder, chunk: ChunkObject) -> str:
        raise Exception(f"dry_run not implemented for {self.__class__.__name__}")
