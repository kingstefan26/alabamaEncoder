# Experimenting with quantization matrices (enable-qm) in SVT-AV1

## TL;DR

* use `--qm-min 0 --qm-max 15 --enable-qm 1` when using CRF
* use `--qm-min 0 --qm-max 15 --enable-qm 1` on animation in VBR
* in most cases, default value min max and `--enable-qm 1` does placebo similar as disabled, but with some free gains here and there. So I recommend keeping
  it enabled

## intro

notes:

* written as `min-max`, so `8-15` is `--qm_min 8 --qm_max 15`
* 8-15 is the default when using enable-qm=1
* using SVT-AV1 fca4581 (release)
* done on 200 frame chunks of a 1080p 24fps video, Blu-ray quality

crf params
used: `--input-depth 10 --crf 18 --tune 0 --film-grain 3 --preset 4 --qm-min x --qm-max x --enable-qm x --scd 0 --enable-overlays 1 --passes 1`

vbr params
used: ` --input-depth 10 --keyint 240 --rc 1 --tbr x --bias-pct 90 --tune 0 --film-grain 3 --preset 4 --qm-min x --qm-max x --enable-qm x --scd 0 --passes 3`

# Tests:

## typical live action

| _CRF 18_ |  size  | kpbs | vmaf  |
|----------|:------:|:----:|:-----:|
| 8-15     | 1106kb | 1061 | 96.03 |
| 0-15     | 1023kb | 981  | 95.95 |
| disabled | 1152kb | 1105 | 96.03 |

subjective eye test: cant tell a difference between the 3

| _VBR 1Mbps_ |  size  | kpbs | vmaf  |
|-------------|:------:|:----:|:-----:|
| 8-15        | 1044kb | 1001 | 96.09 |
| 0-15        | 1047kb | 1004 | 96.06 |
| disabled    | 1042kb | 1000 | 96.09 |

subjective eye test: cant tell a difference between the 3

### Conclusion:

free gains for CRF, no significant effect on VBR

## high motion, heavy fx, action movie

| _CRF 18_ |  size  | kpbs | vmaf  |
|----------|:------:|:----:|:-----:|
| 8-15     | 3904kb | 3744 | 99.67 |
| 0-15     | 3762kb | 3608 | 99.66 |
| disabled | 3914kb | 3753 | 99.67 |

subjective eye test: av1 destroyed fine details as always, couldn't really tell a difference between the 3

| _VBR 2Mbps_ |  size  | kpbs | vmaf  |
|-------------|:------:|:----:|:-----:|
| 8-15        | 2043kb | 1959 | 99.25 |
| 0-15        | 2049kb | 1965 | 99.23 |
| disabled    | 2041kb | 1958 | 99.22 |

subjective eye test: looks a little worse than crf, but the motion hides it well. side by side is hard to tell

### Conclusion:

same as above for live action, but more pronounced

## 2d animation (anime)

| _CRF 18_ |  size  | kpbs | vmaf  |
|----------|:------:|:----:|:-----:|
| 8-15     | 4309kb | 4132 | 97.65 |
| 0-15     | 4646kb | 4456 | 97.87 |
| disabled | 4546kb | 4370 | 97.68 |

subjective eye test: side by side looks the same as input

| _VBR 1.5Mbps_ |  size  | kpbs | vmaf  |
|---------------|:------:|:----:|:-----:|
| 8-15          | 1453kb | 1393 | 94.96 |
| 0-15          | 1438kb | 1380 | 95.50 |
| disabled      | 1450kb | 1390 | 94.77 |

subjective eye test: there is more mosqito noise compared to crf, but they look very similar

### Conclusion:

Use qm when using crf. Vbr 0-15 it seems to be the best metrics but more data needed

## Stop-motion animation

| _CRF 18_ |  size  | kpbs | vmaf  |
|----------|:------:|:----:|:-----:|
| 8-15     | 6102kb | 5853 | 96.85 |
| 0-15     | 5737kb | 5502 | 96.66 |
| disabled | 6251kb | 5995 | 96.85 |

subjective eye test: no noticeable difference, imo 0-15 represents fine details better

| _VBR 3Mbps_ |  size  | kpbs | vmaf  |
|-------------|:------:|:----:|:-----:|
| 8-15        | 3063kb | 2938 | 94.66 |
| 0-15        | 3128kb | 3000 | 94.84 |
| disabled    | 3072kb | 2946 | 94.55 |

subjective eye test: disabled has more blocking artifacts, otherwise no noticeable difference

### Conclusion:

Another win for crf 0-15. Same as for animation: vbr 0-15 maybe the best but more data needed