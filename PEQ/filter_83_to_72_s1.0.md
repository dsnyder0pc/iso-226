### Equal-Loudness Compensation EQ for 72 dB

*Mastering reference 83 dB (default) · listening level 72 dB · scale 1.00 · designed at 44.1 kHz*

**Headroom adjustment: -5.8 dB.** Apply this as a negative preamp / headroom setting. It is the worst case across 44.1/48/96/192 kHz.

**To compare against no correction, play the unfiltered signal at -5.1 dB.** How you apply that attenuation varies from one DSP to the next, so consult your player's documentation — it may be a second preset with its bands switched off, a flat filter carrying only a preamp, or an input trim. The point of the figure is that the two sides then sound the same size, so switching between them compares tonal balance rather than volume — and the louder of two similar presentations almost always sounds better, which would tell you nothing about the filters. It sits 0.7 dB from the headroom above, which is the level the bands add back at 500 Hz — near enough to read off the response plot yourself. It is a rule of thumb calibrated by listening rather than a derived quantity; if your own ears want a slightly different number, they are the better authority. The compensated side should still arrive fuller at the extremes, which is the whole of what you are listening for.

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
