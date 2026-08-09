### Equal-Loudness Compensation EQ for 72 dB

*Mastering reference 83 dB (default) · listening level 72 dB · scale 1.00 · designed at 44.1 kHz*

**Headroom adjustment: -5.8 dB.** Apply this as a negative preamp / headroom setting. It is the worst case across 44.1/48/96/192 kHz.

**To compare against no correction, bypass at -2.4 dB.** Make a second copy of this preset with the five bands switched off and its headroom set to -2.4 dB instead of -5.8 dB. The two then play at the same loudness (ITU-R BS.1770), so switching between them compares tonal balance and nothing else. Left on the same headroom they would differ by 3.4 dB, and the louder of two similar presentations almost always sounds better — which would tell you nothing about the filters.

#### 5 bands (max residual error 0.0430 dB)

A complete full-spectrum correction. The residual error is the deviation these published, rounded values leave against the ideal ISO 226 target — it is quoted for the numbers below, not for an unrounded fit behind them.

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 81.49 | 6.33 | 0.41 |
| 2 | Peak | 368.4 | 1.24 | 0.25 |
| 3 | Peak | 1452 | -1.30 | 0.25 |
| 4 | Peak | 2469 | 0.48 | 0.51 |
| 5 | High Shelf | 10200 | 2.05 | 0.77 |

---

![Frequency response at 72 dB](../images/filter_83_to_72_s1.0.png)

*Published, rounded values (blue) against the ideal ISO 226 target (grey), with the headroom adjustment applied. Most DSPs draw this curve as you type — yours should end up the same shape.*
