# Experimenting with speed in SVT-AV1

## conclusion:

### fr tho, idk what crack they mixed into speed <4 but its not worth it 💀

### params:

* --keyint 999 --rc 1 --tbr x --tune 0 --bias-pct 50 --lp 12 --film-grain 3 --preset x --passes 3

### things to note:

* done on a Ryzen 5 5600G with a zen kenel
* using SVT-AV1 v1.5.0
* BD rate = size / vmaf
* for the % change fields, speed 4 is the baseline

## liveAction_normal.mp4

_Vbr 1000_

| speed | time taken | kpbs | vmaf  | BD Change % | time Change % |
|-------|:----------:|:----:|:-----:|:-----------:|:-------------:|
| 4     |   85.67s   | 990  | 95.39 |    0.0%     |     0.0%      |
| 3     |  140.58s   | 992  | 95.40 |    0.27%    |    64.09%     |
| 2     |  273.80s   | 989  | 95.46 |   -0.16%    |    219.59%    |

## liveAction_highMotion.mkv

_Vbr 2000_

| speed | time taken | kpbs | vmaf  | BD Change % | time Change % |
|-------|:----------:|:----:|:-----:|:-----------:|:-------------:|
| 4     |   74.78s   | 1959 | 99.18 |    0.0%     |     0.0%      |
| 3     |  124.51s   | 1956 | 99.21 |   -0.22%    |    66.51%     |
| 2     |  280.85s   | 1957 | 99.22 |   -0.16%    |    275.57%    |

## liveAction_4k.mp4

_Vbr 4000_

| speed | time taken | kpbs | vmaf  | BD Change % | time Change % |
|-------|:----------:|:----:|:-----:|:-----------:|:-------------:|
| 4     |  249.82s   | 3847 | 95.58 |    0.0%     |     0.0%      |
| 3     |  387.43s   | 3809 | 95.57 |   -0.98%    |    55.08%     |
| 2     |  671.43s   | 3739 | 95.59 |   -2.81%    |    168.75%    |

## liveaction_bright.mkv

_Vbr 1000_

| speed | time taken | kpbs | vmaf  | BD Change % | time Change % |
|-------|:----------:|:----:|:-----:|:-----------:|:-------------:|
| 4     |   75.10s   | 991  | 99.62 |    0.0%     |     0.0%      |
| 3     |  124.69s   | 993  | 99.64 |    0.14%    |    66.02%     |
| 2     |  249.37s   | 988  | 99.67 |   -0.30%    |    232.04%    |

## Animation.mkv

_Vbr 1500_

| speed | time taken | kpbs | vmaf  | BD Change % | time Change % |
|-------|:----------:|:----:|:-----:|:-----------:|:-------------:|
| 4     |   69.51s   | 1388 | 95.37 |    0.0%     |     0.0%      |
| 3     |   99.95s   | 1378 | 95.59 |   -0.99%    |    43.78%     |
| 2     |  205.44s   | 1317 | 95.91 |   -5.69%    |    195.54%    |

## stopmotion.mkv

_Vbr 3000_

| speed | time taken | kpbs | vmaf  | BD Change % | time Change % |
|-------|:----------:|:----:|:-----:|:-----------:|:-------------:|
| 4     |   90.03s   | 2939 | 94.54 |    0.0%     |     0.0%      |
| 3     |  143.96s   | 2962 | 94.71 |    0.60%    |    59.90%     |
| 2     |  287.42s   | 2931 | 94.77 |   -0.51%    |    219.24%    |
