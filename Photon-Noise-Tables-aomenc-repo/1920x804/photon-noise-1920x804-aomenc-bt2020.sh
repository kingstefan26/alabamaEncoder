#!/bin/bash

mkdir 1920x804-BT2020-ISO-Photon
cd 1920x804-BT2020-ISO-Photon

#ISO100-200 BT2020
for i in {100..200..100}
do
/home/bluezakm/aom/aom_build/examples/photon_noise_table --width=1920 --height=804 --iso=$i --transfer-function=smpte2084 --output=1920x804-BT2020-ISO$i.tbl
done

#ISO200-320 BT2020
for i in {200..320..60}
do
/home/bluezakm/aom/aom_build/examples/photon_noise_table --width=1920 --height=804 --iso=$i --transfer-function=smpte2084 --output=1920x804-BT2020-ISO$i.tbl
done

#ISO400-500 BT2020
for i in {400..500..100}
do
/home/bluezakm/aom/aom_build/examples/photon_noise_table --width=1920 --height=804 --iso=$i --transfer-function=smpte2084 --output=1920x804-BT2020-ISO$i.tbl
done

#ISO600-1600 BT2020
for i in {600..1600..200}
do
/home/bluezakm/aom/aom_build/examples/photon_noise_table --width=1920 --height=804 --iso=$i --transfer-function=smpte2084 --output=1920x804-BT2020-ISO$i.tbl
done

#ISO3200-6400 BT2020
for i in {3200..6400..3200}
do
/home/bluezakm/aom/aom_build/examples/photon_noise_table --width=1920 --height=804 --iso=$i --transfer-function=smpte2084 --output=1920x804-BT2020-ISO$i.tbl
done



