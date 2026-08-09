### Equal-Loudness Compensation EQ for 68 dB

*Mastering reference 83 dB (default) · listening level 68 dB · scale 1.00 · designed at 44.1 kHz*

**Headroom adjustment: -7.9 dB.** Apply this as a negative preamp / headroom setting. It is the worst case across 44.1/48/96/192 kHz.

**To compare against no correction, bypass at -3.2 dB.** Make a second copy of this preset with the five bands switched off and its headroom set to -3.2 dB instead of -7.9 dB. The two then play at the same loudness (ITU-R BS.1770), so switching between them compares tonal balance and nothing else. Left on the same headroom they would differ by 4.7 dB, and the louder of two similar presentations almost always sounds better — which would tell you nothing about the filters.

#### 5 bands (max residual error 0.0417 dB)

A complete full-spectrum correction. The residual error is the deviation these published, rounded values leave against the ideal ISO 226 target — it is quoted for the numbers below, not for an unrounded fit behind them.

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 71.28 | 8.85 | 0.41 |
| 2 | Peak | 259.9 | 1.62 | 0.25 |
| 3 | Peak | 634.4 | -0.79 | 0.50 |
| 4 | Peak | 3708 | -0.68 | 0.25 |
| 5 | High Shelf | 10170 | 3.19 | 0.71 |

---

![Frequency response at 68 dB](../images/filter_83_to_68_s1.0.png)

*Published, rounded values (blue) against the ideal ISO 226 target (grey), with the headroom adjustment applied. Most DSPs draw this curve as you type — yours should end up the same shape.*
