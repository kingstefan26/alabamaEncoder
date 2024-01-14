# Experimenting with super resolution in SVT-AV1

### params: same as speed.md

### conclusion:

# not worth it, may yield benefits, dont care didnt ask

### Doing: /mnt/data/liveAction_normal.mp4

Vbr 1000

| _sres mode_ | time taken | kpbs | vmaf  | BD Change % | time Change % |
|-------------|:----------:|:----:|:-----:|:-----------:|:-------------:|
| 0           |   149.67   | 993  | 95.40 |    0.0%     |     0.0%      |
| 1           |   159.77   | 993  | 95.40 |    0.0%     |     6.75%     |
| 2           |   160.16   | 993  | 95.40 |    0.02%    |     7.00%     |
| 3           |   154.59   | 993  | 95.40 |    0.02%    |     3.28%     |

### Doing: /mnt/data/liveAction_highMotion.mkv

Vbr 2000

| _sres mode_ | time taken | kpbs | vmaf  | BD Change % | time Change % |
|-------------|:----------:|:----:|:-----:|:-----------:|:-------------:|
| 0           |  136.45s   | 1956 | 99.21 |    0.0%     |     0.0%      |
| 1           |  133.36s   | 1956 | 99.21 |    0.00%    |    -2.26%     |
| 2           |  139.95s   | 1956 | 99.21 |    0.0%     |     2.56%     |
| 3           |  133.74s   | 1956 | 99.21 |    0.00%    |    -1.98%     |

### Doing: /mnt/data/liveaction_bright.mkv

Vbr 1000

| _sres mode_ | time taken | kpbs | vmaf  | BD Change % | time Change % |
|-------------|:----------:|:----:|:-----:|:-----------:|:-------------:|
| 0           |  140.52s   | 991  | 99.66 |    0.0%     |     0.0%      |
| 1           |  136.04s   | 991  | 99.65 |    0.05%    |    -3.18%     |
| 2           |  145.65s   | 993  | 99.66 |    0.20%    |     3.65%     |
| 3           |  136.32s   | 992  | 99.65 |    0.14%    |    -2.98%     |

ENC1 (SUPERRES MODE 4)
overall VMAF 1%tile avg (positive mean better): 0.014547102010790755%
overall size avg (positive mean worse): -0.02966405713537517%
overall VMAF avg (positive mean better): -0.004899770777030077%
overall SSIM avg (positive mean better): -0.0035386811880550157%
overall Bits Per vmaf avg (positive mean worse): -0.024765208615238777%

ENC2 (SUPERRES MODE 3 WITH DEFAULTS)
overall VMAF 1%tile avg (positive mean better): -0.026554512323063374%
overall size avg (positive mean worse): -0.0021633925937933553%
overall VMAF avg (positive mean better): -0.010857088111648571%
overall SSIM avg (positive mean better): -0.003544204309752841%
overall Bits Per vmaf avg (positive mean worse): 0.00869668195706426%
