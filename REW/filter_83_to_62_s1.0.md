### Equal-Loudness Compensation EQ for 62 dB

*Mastering reference 83 dB (default) · listening level 62 dB · scale 1.00 · designed at 44.1 kHz*

**Headroom adjustment: -11.0 dB.** Apply this as a negative preamp / headroom setting. It is the worst case across 44.1/48/96/192 kHz and is safe for either the essential five bands or all ten.

#### Essential — bands 1–5 (max residual error 0.0984 dB)

A complete full-spectrum correction on its own. Enter these five and stop if you like.

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 115.6 | 12.00 | 0.34 |
| 2 | Peak | 409.0 | -0.47 | 0.48 |
| 3 | Peak | 1547.3 | 0.44 | 0.25 |
| 4 | Peak | 3934.9 | -1.37 | 0.25 |
| 5 | High Shelf | 9902.5 | 4.61 | 0.68 |

#### Refinement — bands 6–10, optional (max residual error with all ten: 0.0864 dB)

These reduce the residual error further. Compare the two traces in the verification plot before deciding whether the extra entry is worth it.

> **These bands round to 0.00 dB at the 0.1 dB entry precision Roon and most DSPs accept, so typing them in by hand changes nothing.** Five bands have already tracked the ISO 226 target to well below audibility; there is no residual left for them to correct. They are kept in the YAML because loading a file costs nothing, and listed here so the claim can be checked rather than taken on trust.

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 6 | Low Shelf | 38.4 | 0.03 | 0.25 |
| 7 | Peak | 173.2 | -0.03 | 2.00 |
| 8 | Peak | 548.3 | 0.01 | 0.25 |
| 9 | Peak | 1886.1 | -0.02 | 0.25 |
| 10 | High Shelf | 7167.3 | 0.03 | 0.25 |
