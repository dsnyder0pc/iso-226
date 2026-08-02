### Equal-Loudness Compensation EQ for 65 dB

*Mastering reference 83 dB (default) · listening level 65 dB · scale 1.00 · designed at 44.1 kHz*

**Headroom adjustment: -9.5 dB.** Apply this as a negative preamp / headroom setting. It is the worst case across 44.1/48/96/192 kHz and is safe for either the essential five bands or all ten.

#### Essential — bands 1–5 (max residual error 0.0535 dB)

A complete full-spectrum correction on its own. Enter these five and stop if you like.

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 66.7 | 10.51 | 0.44 |
| 2 | Peak | 301.9 | 3.06 | 0.25 |
| 3 | Peak | 588.8 | -1.95 | 0.43 |
| 4 | Peak | 3523.8 | -0.83 | 0.25 |
| 5 | High Shelf | 10173.1 | 3.79 | 0.71 |

#### Refinement — bands 6–10, optional (max residual error with all ten: 0.0506 dB)

These reduce the residual error further. Compare the two traces in the verification plot before deciding whether the extra entry is worth it.

> **These bands round to 0.00 dB at the 0.1 dB entry precision Roon and most DSPs accept, so typing them in by hand changes nothing.** Five bands have already tracked the ISO 226 target to well below audibility; there is no residual left for them to correct. They are kept in the YAML because loading a file costs nothing, and listed here so the claim can be checked rather than taken on trust.

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 6 | Low Shelf | 40.0 | -0.00 | 0.70 |
| 7 | Peak | 154.9 | -0.01 | 0.70 |
| 8 | Peak | 574.5 | 0.01 | 0.54 |
| 9 | Peak | 2097.6 | -0.01 | 0.25 |
| 10 | High Shelf | 6633.2 | 0.01 | 0.25 |
