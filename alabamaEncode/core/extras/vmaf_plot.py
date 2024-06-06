import os

import numpy as np
from matplotlib import pyplot as plt

from alabamaEncode.core.context import AlabamaContext
from alabamaEncode.scene.sequence import ChunkSequence


def plot_vmaf(ctx: AlabamaContext, sequence: ChunkSequence, show_bpp=False):
    print("Plotting vmaf...")
    vmaf_scores = ctx.get_kv().get_all("vmaf_frame_scores")
    crfs = ctx.get_kv().get_all("target_vmaf")

    bpp = {}
    pixels_in_frame = sequence.chunks[0].width * sequence.chunks[0].height
    for chunk in sequence.chunks:
        chunk_size_bits = os.path.getsize(chunk.chunk_path) * 8
        bpp[chunk.chunk_index] = (
            chunk_size_bits / pixels_in_frame / chunk.get_frame_count()
        )

    all_scores = []
    for chunk_scores in vmaf_scores.values():
        all_scores.extend(chunk_scores.values())

    plt.figure(figsize=(12, 8))

    plt.plot(all_scores, label="VMAF", color="steelblue")
    plt.ylabel("VMAF Score")
    plt.ylim(0, 100)

    plt.axhline(ctx.vmaf, color="g", linestyle="--", label="Target VMAF")

    crf_values = []
    for chunk_scores in vmaf_scores.values():
        chunk_num = list(vmaf_scores.keys())[
            list(vmaf_scores.values()).index(chunk_scores)
        ]
        crf_values.extend([crfs[chunk_num]] * len(chunk_scores))

    ax1 = plt.gca()
    ax2 = plt.twinx()
    ax2.plot(crf_values, color="darkorange", linestyle="--", label="CRF")
    ax2.set_ylabel("CRF")
    ax2.set_ylim(0, 63)

    if show_bpp:
        # Create a third axis
        ax3 = ax1.twinx()

        # Calculate bpp values for each chunk
        bpp_values = [bpp[int(chunk_num)] for chunk_num in vmaf_scores.keys()]

        # Extend bpp values for each chunk by the number of frames in that chunk
        extended_bpp_values = []
        for chunk_num, bpp_value in zip(vmaf_scores.keys(), bpp_values):
            chunk_frame_count = sequence.chunks[int(chunk_num)].get_frame_count()
            extended_bpp_values.extend([bpp_value] * chunk_frame_count)

        # Plot extended bpp values on the third axis
        ax3.plot(extended_bpp_values, color="purple", linestyle="--", label="BPP")
        ax3.set_ylabel("BPP (rescaled)")

    mean_vmaf = np.mean(all_scores)
    median_vmaf = np.median(all_scores)

    plt.text(
        0.02,
        0.10,
        f"Mean: {mean_vmaf:.2f}\nMedian: {median_vmaf:.2f}\nTarget: {ctx.vmaf}",
        transform=ax1.transAxes,
        fontsize=9,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.5),
    )

    plt.xlabel("Frame")

    if show_bpp:
        plt.title("VMAF Scores, CRFs and BPP")
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        lines3, labels3 = ax3.get_legend_handles_labels()
        ax2.legend(
            lines1 + lines2 + lines3, labels1 + labels2 + labels3, loc="lower right"
        )
    else:
        plt.title("VMAF against CRF")
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax2.legend(lines1 + lines2, labels1 + labels2, loc="lower right")

    plt.savefig(f"{ctx.output_folder}/vmaf_plot.svg")
    plt.close()
