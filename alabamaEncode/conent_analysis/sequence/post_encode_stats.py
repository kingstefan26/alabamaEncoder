from alabamaEncode.core.extras.vmaf_plot import plot_vmaf
from alabamaEncode.core.final_touches import (
    print_stats,
    generate_previews,
    create_torrent_file,
)
from alabamaEncode.metrics.metric import Metric


def run_post_encode_stats(ctx):
    if ctx.generate_stats:
        print_stats(
            output_folder=ctx.output_folder,
            output=ctx.output_file,
            title=ctx.get_title(),
        )
        target_metric = ctx.get_metric_target()[0]
        if ctx.calc_final_vmaf and (
            target_metric == Metric.VMAF or target_metric == Metric.XPSNR
        ):
            plot_vmaf(ctx, ctx.chunk_sequence)

    if ctx.generate_previews:
        generate_previews(input_file=ctx.output_file, output_folder=ctx.output_folder)
        create_torrent_file(
            video=ctx.output_file,
            encoder_name=ctx.encoder_name,
            output_folder=ctx.output_folder,
        )
    return ctx
