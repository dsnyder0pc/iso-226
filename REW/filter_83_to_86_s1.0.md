### Equal-Loudness Compensation EQ for 86 dB

*Mastering reference 83 dB (default) · listening level 86 dB · scale 1.00 · designed at 44.1 kHz*

**Headroom adjustment: -0.2 dB.** Apply this as a negative preamp / headroom setting. It is the worst case across 44.1/48/96/192 kHz and is safe for either the essential five bands or all ten.

#### Essential — bands 1–5 (max residual error 0.0315 dB)

A complete full-spectrum correction on its own. Enter these five and stop if you like.

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 39.2 | -2.61 | 0.27 |
| 2 | Peak | 267.7 | -0.17 | 0.57 |
| 3 | Peak | 853.6 | -0.00 | 1.62 |
| 4 | Peak | 2884.1 | 0.10 | 0.25 |
| 5 | High Shelf | 9761.3 | -0.51 | 0.84 |

#### Refinement — bands 6–10, optional (max residual error with all ten: 0.0197 dB)

These reduce the residual error further. Compare the two traces in the verification plot before deciding whether the extra entry is worth it.

> **These bands round to 0.00 dB at the 0.1 dB entry precision Roon and most DSPs accept, so typing them in by hand changes nothing.** Five bands have already tracked the ISO 226 target to well below audibility; there is no residual left for them to correct. They are kept in the YAML because loading a file costs nothing, and listed here so the claim can be checked rather than taken on trust.

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 6 | Low Shelf | 41.5 | 0.02 | 0.26 |
| 7 | Peak | 145.7 | -0.02 | 0.25 |
| 8 | Peak | 655.0 | 0.00 | 1.04 |
| 9 | Peak | 1827.4 | 0.00 | 1.01 |
| 10 | High Shelf | 7125.0 | 0.00 | 0.25 |
