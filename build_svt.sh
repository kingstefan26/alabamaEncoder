cd ~/dev/SVT-AV1/
git pull
cd ~/dev/SVT-AV1/Build/linux/
./build.sh clean
./build.sh cc=clang cxx=clang++ enable-lto static native release
rm ~/.local/opt/SvtAv1EncApp
mv ~/dev/SVT-AV1/Bin/Release/SvtAv1EncApp ~/.local/opt/SvtAv1EncApp
chmod +x ~/.local/opt/SvtAv1EncApp
SvtAv1EncApp