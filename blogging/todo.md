## things that I need to test/experiment in svtav1:

- [ ] speed 3 vs 4 vs 2, my uneducated guess is that speed 4 is much faster than 3 and the difference is hot air BUT
  need data to back that up
- [X] `chroma qindex offset`'s, blueswordm a while back has recommended u-dc:-2 u-ac:-2 v-dc:-2 v-ac:-2 but need: to
  understand it & benchmark it
- [ ] benchmark & test --tune 0 compared to 1. For example, why is 1 default if 0 is so better??
- [ ] benchmark & test --enable-overlays
- [ ] experiment with superresolution
- [ ] experiment with S frames (golden refreshes, etc)
- [ ] experiment with reference scaling
- [ ] tile cols/rows effect on efficiency
- [ ] experiment with gop, open gop? 9999 frame gop with s frames? etc
- [ ] undershoot-pct overshoot-pct mbr-overshoot-pct & capped crf for uhd encoding