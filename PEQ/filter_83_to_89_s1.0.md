### Equal-Loudness Compensation EQ for 89 dB

*Mastering reference 83 dB (default) · listening level 89 dB · scale 1.00 · designed at 44.1 kHz*

**Headroom adjustment: -0.3 dB.** Apply this as a negative preamp / headroom setting. It is the worst case across 44.1/48/96/192 kHz.

**To compare against no correction, play the unfiltered signal at -0.7 dB.** How you apply that attenuation varies from one DSP to the next, so consult your player's documentation — it may be a second preset with its bands switched off, a flat filter carrying only a preamp, or an input trim. The point of the figure is that the two sides then sound the same size, so switching between them compares tonal balance rather than volume — and the louder of two similar presentations almost always sounds better, which would tell you nothing about the filters. It sits 0.4 dB from the headroom above, which is the level the bands add back at 500 Hz — near enough to read off the response plot yourself. It is a rule of thumb calibrated by listening rather than a derived quantity; if your own ears want a slightly different number, they are the better authority. The compensated side should still arrive fuller at the extremes, which is the whole of what you are listening for.

#### 5 bands (max residual error 0.0229 dB)

A complete full-spectrum correction. The residual error is the deviation these published, rounded values leave against the ideal ISO 226 target — it is quoted for the numbers below, not for an unrounded fit behind them.

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 62.4 | -3.61 | 0.42 |
| 2 | Peak | 219.6 | -0.76 | 0.25 |
| 3 | Peak | 617.1 | 0.31 | 0.59 |
| 4 | Peak | 3422 | 0.27 | 0.25 |
| 5 | High Shelf | 10160 | -1.26 | 0.72 |

---

![Frequency response at 89 dB](../images/filter_83_to_89_s1.0.png)

*Published, rounded values (blue) against the ideal ISO 226 target (grey), with the headroom adjustment applied. Most DSPs draw this curve as you type — yours should end up the same shape.*
