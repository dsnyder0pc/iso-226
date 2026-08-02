### Equal-Loudness Compensation EQ for 74 dB

*Mastering reference 83 dB (default) · listening level 74 dB · scale 1.00 · designed at 44.1 kHz*

**Headroom adjustment: -4.8 dB.** Apply this as a negative preamp / headroom setting. It is the worst case across 44.1/48/96/192 kHz and is safe for either the essential five bands or all ten.

#### Essential — bands 1–5 (max residual error 0.0666 dB)

A complete full-spectrum correction on its own. Enter these five and stop if you like.

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 38.7 | 7.88 | 0.26 |
| 2 | Peak | 262.6 | 0.50 | 0.63 |
| 3 | Peak | 927.0 | 0.00 | 0.79 |
| 4 | Peak | 2909.6 | -0.32 | 0.36 |
| 5 | High Shelf | 9885.3 | 1.48 | 0.86 |

#### Refinement — bands 6–10, optional (max residual error with all ten: 0.0513 dB)

These reduce the residual error further. Compare the two traces in the verification plot before deciding whether the extra entry is worth it.

> **These bands round to 0.00 dB at the 0.1 dB entry precision Roon and most DSPs accept, so typing them in by hand changes nothing.** Five bands have already tracked the ISO 226 target to well below audibility; there is no residual left for them to correct. They are kept in the YAML because loading a file costs nothing, and listed here so the claim can be checked rather than taken on trust.

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 6 | Low Shelf | 28.9 | 0.02 | 0.69 |
| 7 | Peak | 230.5 | -0.03 | 0.25 |
| 8 | Peak | 481.3 | 0.02 | 2.00 |
| 9 | Peak | 1836.8 | 0.01 | 0.25 |
| 10 | High Shelf | 7824.6 | -0.00 | 0.26 |
