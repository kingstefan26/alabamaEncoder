# Testing tunes in svtav1

you can see data in `/alabamaEncode/experiments/data/tunes/Testing SvtAv1 TUNES, speed 4 CRF.json`,
after analyzing the data using functions from `/alabamaEncode/experiments/Svtav1Tunes.py`

# I conclude that `--tune 2` is harmful to encode speed, and tune provides ~7% smaller size with no loss in quality

### more in depth:

* test was done across the whole crf range on objective-fast-1, speed 4 <br> with tune 1 being control
* done by taking average differences between test and control and then averaging those
* code linked above
* take the speed with a grain of salt since my pc was not idle but the statistics should average that out
* percentages rounded to 2 decimal places

### TUNE 0

| metric        | how to interpret | % difference |
|---------------|------------------|--------------|
| VMAF 1%tile   | higher better    | -0.6%        |
| size          | higher worse     | -7.06%       |
| VMAF          | higher better    | -0.55%       |
| SSIM          | higher better    | -0.07%       |
| Bits Per vmaf | higher worse     | -6.55%       |
| Enccode time  | higher worse     | -4.37%       |

### TUNE 2

| metric        | how to interpret | % difference |
|---------------|------------------|--------------|
| VMAF 1%tile   | higher better    | -0.00%       |
| size          | higher worse     | -0.00%       |
| VMAF          | higher better    | -0.00%       |
| SSIM          | higher better    | -0.00%       |
| Bits Per vmaf | higher worse     | 0.00%        |
| Enccode time  | higher worse     | 9.60%        |