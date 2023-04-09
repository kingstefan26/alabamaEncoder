#!/bin/bash

mkdir 1920x1032-SRGB-ISO-Photon
cd 1920x1032-SRGB-ISO-Photon

#ISO100-200 SRGB
for i in {100..200..100}
do
/home/bluezakm/aom/aom_build/examples/photon_noise_table --width=1920 --height=1032 --iso=$i --transfer-function=srgb --output=1920x1032-SRGB-ISO$i.tbl
done

#ISO200-320 SRGB
for i in {200..320..60}
do
/home/bluezakm/aom/aom_build/examples/photon_noise_table --width=1920 --height=1032 --iso=$i --transfer-function=srgb --output=1920x1032-SRGB-ISO$i.tbl
done

#ISO400-500 SRGB
for i in {400..500..100}
do
/home/bluezakm/aom/aom_build/examples/photon_noise_table --width=1920 --height=1032 --iso=$i --transfer-function=srgb --output=1920x1032-SRGB-ISO$i.tbl
done

#ISO600-1600 SRGB
for i in {600..1600..200}
do
/home/bluezakm/aom/aom_build/examples/photon_noise_table --width=1920 --height=1032 --iso=$i --transfer-function=srgb --output=1920x1032-SRGB-ISO$i.tbl
done

#ISO3200-6400 SRGB
for i in {3200..6400..3200}
do
/home/bluezakm/aom/aom_build/examples/photon_noise_table --width=1920 --height=1032 --iso=$i --transfer-function=srgb --output=1920x1032-SRGB-ISO$i.tbl
done



