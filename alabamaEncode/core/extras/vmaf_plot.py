import numpy as np
from matplotlib import pyplot as plt

from alabamaEncode.core.context import AlabamaContext


def plot_vmaf(ctx: AlabamaContext):
    print("Plotting vmaf...")
    vmaf_scores = ctx.get_kv().get_all("vmaf_frame_scores")
    crfs = ctx.get_kv().get_all("target_vmaf")

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
    plt.title("VMAF Scores and CRFs")

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, loc="lower right")

    plt.savefig(f"{ctx.output_folder}/vmaf_plot.svg")
    plt.close()
