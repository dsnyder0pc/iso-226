### Equal-Loudness Compensation EQ for 85 dB

*Mastering reference 83 dB (default) · listening level 85 dB · scale 1.00 · designed at 44.1 kHz*

**Headroom adjustment: -0.1 dB.** Apply this as a negative preamp / headroom setting. It is the worst case across 44.1/48/96/192 kHz and is safe for either the essential five bands or all ten.

#### Essential — bands 1–5 (max residual error 0.0172 dB)

A complete full-spectrum correction on its own. Enter these five and stop if you like.

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 39.3 | -1.75 | 0.26 |
| 2 | Peak | 280.2 | -0.12 | 0.66 |
| 3 | Peak | 927.0 | 0.01 | 0.39 |
| 4 | Peak | 2910.3 | 0.07 | 0.40 |
| 5 | High Shelf | 9868.3 | -0.32 | 0.88 |

#### Refinement — bands 6–10, optional (max residual error with all ten: 0.0159 dB)

These reduce the residual error further. Compare the two traces in the verification plot before deciding whether the extra entry is worth it.

> **These bands round to 0.00 dB at the 0.1 dB entry precision Roon and most DSPs accept, so typing them in by hand changes nothing.** Five bands have already tracked the ISO 226 target to well below audibility; there is no residual left for them to correct. They are kept in the YAML because loading a file costs nothing, and listed here so the claim can be checked rather than taken on trust.

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 6 | Low Shelf | 39.1 | -0.00 | 1.43 |
| 7 | Peak | 152.6 | 0.01 | 0.31 |
| 8 | Peak | 496.9 | -0.01 | 0.71 |
| 9 | Peak | 1816.7 | -0.01 | 0.61 |
| 10 | High Shelf | 7825.5 | -0.00 | 0.36 |
