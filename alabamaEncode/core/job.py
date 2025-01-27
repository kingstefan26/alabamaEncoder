import hashlib
import os
import sys

from alabamaEncode.cli.cli_setup.paths import parse_paths
from alabamaEncode.cli.cli_setup.ratecontrol import parse_rd
from alabamaEncode.cli.cli_setup.res_preset import parse_resolution_presets
from alabamaEncode.cli.cli_setup.video_filters import parse_video_filters
from alabamaEncode.conent_analysis.pipelines import (
    setup_chunk_analyze_chain,
)
from alabamaEncode.conent_analysis.sequence.args_tune import tune_args_for_fdlty_or_apl
from alabamaEncode.conent_analysis.sequence.autocrop import do_autocrop
from alabamaEncode.conent_analysis.sequence.concat import concat
from alabamaEncode.conent_analysis.sequence.denoise_filtering import setup_denoise
from alabamaEncode.conent_analysis.sequence.encoding_tiles import setup_tiles
from alabamaEncode.conent_analysis.sequence.post_encode_cleanup import (
    run_post_encode_cleanup,
)
from alabamaEncode.conent_analysis.sequence.post_encode_stats import (
    run_post_encode_stats,
)
from alabamaEncode.conent_analysis.sequence.run_encode_jobs import run_encode_jobs
from alabamaEncode.conent_analysis.sequence.scene_detection import do_scene_detection
from alabamaEncode.conent_analysis.sequence.scrape_hdr_meta import scrape_hdr_metadata
from alabamaEncode.conent_analysis.sequence.sequence_autograin import setup_autograin
from alabamaEncode.conent_analysis.sequence.setup_celery import setup_celery
from alabamaEncode.conent_analysis.sequence.setup_chunk_encoder import (
    setup_chunk_encoder,
)
from alabamaEncode.conent_analysis.sequence.setup_chunk_encoders import (
    setup_chunk_encoders,
)
from alabamaEncode.conent_analysis.sequence.taget_ssimdb import setup_ssimdb_target
from alabamaEncode.conent_analysis.sequence.x264_tune import get_ideal_x264_tune
from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.core.extras.ws_update import WebsiteUpdate
from alabamaEncode.metrics.impl.vmaf import (
    download_vmaf_models_wrapper,
)


class AlabamaEncodingJob:
    def __init__(self, ctx):
        self.ctx = ctx
        self.websiteUpdate = WebsiteUpdate(ctx)
        self.finished_callback = None

        self.serialise_folder = self.get_serialise_folder()

        sha1 = hashlib.sha1()
        sha1.update(str.encode(self.ctx.get_title()))
        hash_as_hex = sha1.hexdigest()
        title_hash = int(hash_as_hex, 16) % sys.maxsize
        self.serialise_file = os.path.join(
            self.serialise_folder,
            f"{title_hash}" f".json",
        )

    @staticmethod
    def get_serialise_folder():
        serialise_folder = os.path.expanduser("~/.alabamaEncoder/jobs")
        if not os.path.exists(serialise_folder):
            os.makedirs(serialise_folder)
        return serialise_folder

    @staticmethod
    def get_saved_serialised_jobs():
        for file in os.listdir(AlabamaEncodingJob.get_serialise_folder()):
            with open(
                os.path.join(AlabamaEncodingJob.get_serialise_folder(), file)
            ) as f:
                yield f.read()

    def save(self):
        with open(self.serialise_file, "w") as f:
            f.write(self.ctx.to_json())

    def delete(self):
        if os.path.exists(self.serialise_file):
            os.remove(self.serialise_file)

    @staticmethod
    def load_from_file(json_job):
        ctx = AlabamaContext().from_json(json_job)
        creation_pipeline = [
            parse_paths,
            parse_rd,
            parse_resolution_presets,
            parse_video_filters,
        ]
        for pipeline_item in creation_pipeline:
            ctx = pipeline_item(ctx)

        return AlabamaEncodingJob(ctx)

    async def run_pipeline(self):
        self.save()

        if not os.path.exists(self.ctx.output_file):
            pipeline = [
                setup_celery,
                do_scene_detection,
                download_vmaf_models_wrapper,
                setup_chunk_analyze_chain,
                setup_chunk_encoder,
                scrape_hdr_metadata,
                tune_args_for_fdlty_or_apl,
                do_autocrop,
                setup_tiles,
                setup_denoise,
                setup_autograin,
                setup_ssimdb_target,
                get_ideal_x264_tune,
                setup_chunk_encoders,
                run_encode_jobs,
                concat,
                run_post_encode_stats,
                run_post_encode_cleanup,
            ]

            for func in pipeline:
                # if async await, if not run normally
                self.ctx = (
                    await func(self.ctx)
                    if func.__code__.co_flags & 0x80
                    else func(self.ctx)
                )

        if self.finished_callback is not None:
            self.finished_callback()

        self.delete()
