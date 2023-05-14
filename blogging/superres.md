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
