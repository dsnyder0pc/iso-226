### Equal-Loudness Compensation EQ for 78 dB

*Mastering reference 83 dB (default) · listening level 78 dB · scale 1.00 · designed at 44.1 kHz*

**Headroom adjustment: -2.7 dB.** Apply this as a negative preamp / headroom setting. It is the worst case across 44.1/48/96/192 kHz.

**To compare against no correction, bypass at -2.8 dB.** Make a second copy of this preset with the five bands switched off and its headroom set to -2.8 dB instead of -2.7 dB. That matches the two across 500 Hz–5 kHz, the band the ear judges level over, so switching between them compares tonal balance rather than volume — and the louder of two similar presentations almost always sounds better, which would tell you nothing about the filters. The figure lands close to the headroom above because the correction is 0 dB at 1 kHz by definition; the compensated side should still arrive fuller at the extremes, which is the whole of what you are listening for.

#### 5 bands (max residual error 0.0216 dB)

A complete full-spectrum correction. The residual error is the deviation these published, rounded values leave against the ideal ISO 226 target — it is quoted for the numbers below, not for an unrounded fit behind them.

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 94.85 | 2.87 | 0.38 |
| 2 | Peak | 313.7 | 0.22 | 0.25 |
| 3 | Peak | 899.1 | -0.08 | 0.42 |
| 4 | Peak | 2913 | -0.21 | 0.25 |
| 5 | High Shelf | 10070 | 0.97 | 0.76 |

---

![Frequency response at 78 dB](../images/filter_83_to_78_s1.0.png)

*Published, rounded values (blue) against the ideal ISO 226 target (grey), with the headroom adjustment applied. Most DSPs draw this curve as you type — yours should end up the same shape.*
