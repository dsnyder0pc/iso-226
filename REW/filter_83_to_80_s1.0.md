### Equal-Loudness Compensation EQ for 80 dB

*Mastering reference 83 dB (default) · listening level 80 dB · scale 1.00 · designed at 44.1 kHz*

**Headroom adjustment: -1.6 dB.** Apply this as a negative preamp / headroom setting. It is the worst case across 44.1/48/96/192 kHz and is safe for either the essential five bands or all ten.

#### Essential — bands 1–5 (max residual error 0.0218 dB)

A complete full-spectrum correction on its own. Enter these five and stop if you like.

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 38.2 | 2.62 | 0.27 |
| 2 | Peak | 240.8 | 0.18 | 0.56 |
| 3 | Peak | 967.6 | -0.00 | 0.31 |
| 4 | Peak | 2822.1 | -0.11 | 0.43 |
| 5 | High Shelf | 9889.9 | 0.48 | 0.89 |

#### Refinement — bands 6–10, optional (max residual error with all ten: 0.0197 dB)

These reduce the residual error further. Compare the two traces in the verification plot before deciding whether the extra entry is worth it.

> **These bands round to 0.00 dB at the 0.1 dB entry precision Roon and most DSPs accept, so typing them in by hand changes nothing.** Five bands have already tracked the ISO 226 target to well below audibility; there is no residual left for them to correct. They are kept in the YAML because loading a file costs nothing, and listed here so the claim can be checked rather than taken on trust.

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 6 | Low Shelf | 38.9 | 0.00 | 1.17 |
| 7 | Peak | 152.6 | 0.01 | 0.39 |
| 8 | Peak | 496.9 | -0.00 | 0.25 |
| 9 | Peak | 1816.7 | 0.00 | 0.25 |
| 10 | High Shelf | 7825.4 | -0.00 | 1.87 |
