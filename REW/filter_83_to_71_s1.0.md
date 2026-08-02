### Equal-Loudness Compensation EQ for 71 dB

*Mastering reference 83 dB (default) · listening level 71 dB · scale 1.00 · designed at 44.1 kHz*

**Headroom adjustment: -6.3 dB.** Apply this as a negative preamp / headroom setting. It is the worst case across 44.1/48/96/192 kHz and is safe for either the essential five bands or all ten.

#### Essential — bands 1–5 (max residual error 0.0565 dB)

A complete full-spectrum correction on its own. Enter these five and stop if you like.

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 97.1 | 6.91 | 0.37 |
| 2 | Peak | 225.8 | 0.32 | 0.25 |
| 3 | Peak | 911.2 | 0.01 | 0.45 |
| 4 | Peak | 2928.1 | -0.52 | 0.25 |
| 5 | High Shelf | 10115.2 | 2.36 | 0.74 |

#### Refinement — bands 6–10, optional (max residual error with all ten: 0.0437 dB)

These reduce the residual error further. Compare the two traces in the verification plot before deciding whether the extra entry is worth it.

> **These bands round to 0.00 dB at the 0.1 dB entry precision Roon and most DSPs accept, so typing them in by hand changes nothing.** Five bands have already tracked the ISO 226 target to well below audibility; there is no residual left for them to correct. They are kept in the YAML because loading a file costs nothing, and listed here so the claim can be checked rather than taken on trust.

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 6 | Low Shelf | 39.8 | -0.01 | 2.00 |
| 7 | Peak | 154.9 | 0.01 | 0.38 |
| 8 | Peak | 574.5 | 0.01 | 0.25 |
| 9 | Peak | 2097.6 | -0.02 | 0.25 |
| 10 | High Shelf | 6633.2 | 0.01 | 0.25 |
