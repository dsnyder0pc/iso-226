### Equal-Loudness Compensation EQ for 80 dB

*Mastering reference 83 dB (default) · listening level 80 dB · scale 1.00 · designed at 44.1 kHz*

**Headroom adjustment: -1.6 dB.** Apply this as a negative preamp / headroom setting. It is the worst case across 44.1/48/96/192 kHz.

**To compare against no correction, play the unfiltered signal at -1.6 dB.** How you apply that attenuation varies from one DSP to the next, so consult your player's documentation — it may be a second preset with its bands switched off, a flat filter carrying only a preamp, or an input trim. The point of the figure is that the two sides then sound the same size, so switching between them compares tonal balance rather than volume — and the louder of two similar presentations almost always sounds better, which would tell you nothing about the filters. That is the headroom figure above, unchanged: this close to the mastering reference the correction moves the level by less than anyone can hear, so one setting serves both sides. It is a rule of thumb calibrated by listening rather than a derived quantity; if your own ears want a slightly different number, they are the better authority. The compensated side should still arrive fuller at the extremes, which is the whole of what you are listening for.

#### 5 bands (max residual error 0.0217 dB)

A complete full-spectrum correction. The residual error is the deviation these published, rounded values leave against the ideal ISO 226 target — it is quoted for the numbers below, not for an unrounded fit behind them.

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 38.22 | 2.62 | 0.27 |
| 2 | Peak | 240.8 | 0.18 | 0.56 |
| 3 | Peak | 967.6 | -0.00 | 0.31 |
| 4 | Peak | 2822 | -0.11 | 0.43 |
| 5 | High Shelf | 9890 | 0.48 | 0.89 |

---

![Frequency response at 80 dB](../images/filter_83_to_80_s1.0.png)

*Published, rounded values (blue) against the ideal ISO 226 target (grey), with the headroom adjustment applied. Most DSPs draw this curve as you type — yours should end up the same shape.*
