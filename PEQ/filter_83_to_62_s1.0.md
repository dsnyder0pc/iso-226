### Equal-Loudness Compensation EQ for 62 dB

*Mastering reference 83 dB (default) · listening level 62 dB · scale 1.00 · designed at 44.1 kHz*

**Headroom adjustment: -11.0 dB.** Apply this as a negative preamp / headroom setting. It is the worst case across 44.1/48/96/192 kHz.

**To compare against no correction, play the unfiltered signal at -9.8 dB.** How you apply that attenuation varies from one DSP to the next, so consult your player's documentation — it may be a second preset with its bands switched off, a flat filter carrying only a preamp, or an input trim. The point of the figure is that the two sides then sound the same size, so switching between them compares tonal balance rather than volume — and the louder of two similar presentations almost always sounds better, which would tell you nothing about the filters. It sits 1.2 dB from the headroom above, which is the level the bands add back at 500 Hz — near enough to read off the response plot yourself. It is a rule of thumb calibrated by listening rather than a derived quantity; if your own ears want a slightly different number, they are the better authority. The compensated side should still arrive fuller at the extremes, which is the whole of what you are listening for.

#### 5 bands (max residual error 0.0925 dB)

A complete full-spectrum correction. The residual error is the deviation these published, rounded values leave against the ideal ISO 226 target — it is quoted for the numbers below, not for an unrounded fit behind them.

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 116.4 | 12.00 | 0.34 |
| 2 | Peak | 449.9 | -0.62 | 0.45 |
| 3 | Peak | 1600 | 0.75 | 0.25 |
| 4 | Peak | 3632 | -1.63 | 0.27 |
| 5 | High Shelf | 9973 | 4.67 | 0.66 |

---

![Frequency response at 62 dB](../images/filter_83_to_62_s1.0.png)

*Published, rounded values (blue) against the ideal ISO 226 target (grey), with the headroom adjustment applied. Most DSPs draw this curve as you type — yours should end up the same shape.*
