FROM ubuntu:latest AS build-stage

WORKDIR /build

SHELL ["/bin/bash", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
RUN rm -f /etc/apt/apt.conf.d/docker-clean; echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache
RUN --mount=target=/var/lib/apt/lists,type=cache,sharing=locked --mount=target=/var/cache/apt,type=cache,sharing=locked
RUN apt-get update -qq && apt-get --no-install-recommends -y install git wget autoconf automake build-essential cmake git-core libass-dev libfreetype6-dev libgnutls28-dev libmp3lame-dev libsdl2-dev libtool libva-dev libvdpau-dev libvorbis-dev libxcb1-dev libzimg-dev libxcb-shm0-dev libxcb-xfixes0-dev meson ninja-build pkg-config texinfo wget yasm zlib1g-dev nasm libx265-dev libnuma-dev libx264-dev libvpx-dev libfdk-aac-dev libopus-dev
RUN git config --global http.sslverify false
RUN mkdir -p ~/ffmpeg_sources ~/bin
RUN cd ~/ffmpeg_sources && git -C SVT-AV1 pull 2> /dev/null || git clone --depth 1 https://gitlab.com/AOMediaCodec/SVT-AV1.git && mkdir -p SVT-AV1/build && cd SVT-AV1/build && PATH="$HOME/bin:$PATH" cmake -G "Unix Makefiles" -DCMAKE_INSTALL_PREFIX="$HOME/ffmpeg_build" -DCMAKE_BUILD_TYPE=Release -DBUILD_DEC=OFF -DBUILD_SHARED_LIBS=OFF .. && PATH="$HOME/bin:$PATH" make -j$(grep -c ^processor /proc/cpuinfo) && make install
RUN cd ~/ffmpeg_sources && wget --no-check-certificate -O ffmpeg-snapshot.tar.bz2 https://ffmpeg.org/releases/ffmpeg-snapshot.tar.bz2 && tar xjvf ffmpeg-snapshot.tar.bz2
RUN cd ~/ffmpeg_sources/ffmpeg && PATH="$HOME/bin:$PATH" PKG_CONFIG_PATH="$HOME/ffmpeg_build/lib/pkgconfig" ./configure   --prefix="$HOME/ffmpeg_build"   --pkg-config-flags="--static"   --extra-cflags="-I$HOME/ffmpeg_build/include"   --extra-ldflags="-L$HOME/ffmpeg_build/lib"   --extra-libs="-lpthread -lm"   --ld="g++"   --bindir="$HOME/bin"   --enable-gpl --enable-libass --enable-libzimg --enable-libfdk-aac   --enable-libfreetype   --enable-libmp3lame   --enable-libopus   --enable-libsvtav1  --enable-libvorbis   --enable-libvpx   --enable-libx264   --enable-libx265   --enable-nonfree && PATH="$HOME/bin:$PATH" make -j$(grep -c ^processor /proc/cpuinfo) && make install
# update the path to include ffmpeg
ENV PATH="/root/bin:${PATH}"
RUN ~/bin/ffmpeg -encoders
# cleanup build dirs
RUN rm -rf ~/ffmpeg_sources

# install python 3.10
RUN apt-get update && apt-get install -y python3.10 python3-pip
# copy requirements.txt and install
COPY requirements.txt .
RUN pip3 install -r requirements.txt
# copy .
COPY . /app
WORKDIR /app
# Allow celery to run as root
ENV C_FORCE_ROOT="true"
# run celery app
CMD ["celery", "-A", "paraliezeMeHoe.ThaVaidioEncoda", "worker", "--loglevel=info", "--autoscale","1"]
