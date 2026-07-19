# ISO 226 Equal-Loudness Compensation PEQ Generator

This repository provides a utility to generate Parametric EQ (PEQ) filters that compensate for the human ear's frequency response variation at different playback levels. The filters track the **ISO 226 equal-loudness contours** relative to a reference level of 83 dB SPL (Sound Pressure Level) to ensure a consistent perceived tonal balance at any volume.

It also includes a verification tool to check the accuracy of the generated filter cascades against the ideal ISO contours.

---

## Introduction & Context

The human ear does not perceive all frequencies equally. Crucially, our sensitivity to bass (low frequencies) and treble (high frequencies) drops significantly as the overall volume level decreases. This phenomenon is standardized in **ISO 226**.

To maintain a natural and consistent tonal balance, audio playback systems ideally need dynamic loudness compensation—where EQ curves dynamically adjust based on the current volume level. However, achieving real-time feedback from a volume control or room SPL meter in playback ecosystems like **Roon** is technically challenging.

This project solves that problem by generating distinct static PEQ presets for common listening levels:

*   **Low (~65 dB)**: Used for quiet listening (e.g., when family members are watching TV in adjacent rooms or late-night listening). Needs significant bass and treble boost.
*   **Medium (~75 dB)**: Used for casual longer listening sessions (e.g., weekend background music). Needs mild bass and treble compensation.
*   **High (~85 dB)**: Used for active demo/loud listening sessions. At levels above 83 dB, human hearing becomes slightly more sensitive to low/high frequencies, requiring minor attenuation (negative gain) relative to the flat reference.

This approach offers a practical, high-fidelity alternative to the classic "one-size-fits-all" loudness switches found on vintage receivers (like the Pioneer SX-780 driving Pioneer HPM 100 speakers), most of which were either on or off and not level-aware.

### Digital Headroom & Clipping Prevention
Because equal-loudness compensation requires boosts in the low and high frequencies, applying these filters digitally can exceed `0 dB` and cause digital clipping (distortion). To prevent this, there are two primary methods:
1.  **Midrange Attenuation (Only Cuts)**: Designing filters that only cut the mids (similar to how vintage Yamaha variable loudness circuits behave). While mathematically equivalent, this is complex to configure as PEQ bands.
2.  **Loudness Boosts + Preamp Attenuation**: Keeping the intuitive boosting filters (low/high shelves) and applying a global preamp reduction (headroom adjustment) equal to the highest peak of the combined filter response. This is the industry-standard method for DSP systems like Roon or miniDSP.

This project implements **Option 2**. The generator calculates the exact peak gain of the combined response and outputs the recommended negative preamp offset to ensure the entire filter curve remains at or below `0 dB`.

---

## How It Works

1.  **Ideal Target Calculation**: Using standard ISO 226 coefficients, the ideal SPL curve is calculated for both the target playback level and the 83 dB reference level.
2.  **Optimization/Curve Fitting**: The target gains for the [BASE_FILTERS](file:///home/dsnyder/src/iso-226/loudness-filters.py#L28) are optimized using `scipy.optimize.curve_fit` to closely match the ideal delta curve.
3.  **Biquad Calculation**: Using Robert Bristow-Johnson's Audio EQ Cookbook formulas implemented in `get_biquad_coefs`, it designs digital biquad filter coefficients for low-shelf, high-shelf, and peak filters.
4.  **Headroom Calculation**: Evaluates the combined response and computes the required negative headroom offset to keep peak gain below 0 dB.
5.  **Visualization & Tables**: Generates frequency response plots and outputs a formatted Markdown table detailing the PEQ bands and the required headroom adjustment offset.

---

## Requirements

Ensure you have Python 3 and the dependencies listed in [requirements.txt](file:///home/dsnyder/src/iso-226/requirements.txt) installed:

```bash
pip install -r requirements.txt
```

---

## Usage

### 1. Generate PEQ Filters
Run the generator script by specifying your target average listening level in dB:

```bash
python loudness-filters.py --level <target_db>
```

*   `--level` (float, default: `65.0`): The target average room sound pressure level (SPL) in dB.

### 2. Verify Residual Error
Run the verification script to check the deviation of the PEQ filters against the ideal contours:

```bash
python check.py --level <target_db>
```

*   If the corresponding `filter-xxdb.md` does not exist, the script automatically invokes `loudness-filters.py` to generate it.
*   It calculates and outputs the maximum residual error to the terminal.
*   It saves an error deviation plot as `iso_226_filter_error_for_xxdb.png`.

---

## The Math Behind It

### ISO 226 Equal-Loudness Contour Formula
The sound pressure level ($L_p$, in dB SPL) for a given phon level ($L_N$) at frequency $f$ is given by:

$$L_p = \frac{10.0}{\alpha_f} \log_{10}(A_f) - L_U + 94.0$$

where:

$$A_f = 4.47 \times 10^{-3} \left(10^{0.025 L_N} - 1.15\right) + \left(0.4 \times 10^{\frac{T_f + L_U}{10} - 9.0}\right)^{\alpha_f}$$

*   $\alpha_f$ (from standard coefficients) represents the exponent factor at frequency $f$.
*   $L_U$ (from standard coefficients) represents the magnitude factor at frequency $f$.
*   $T_f$ (from standard coefficients) represents the threshold of hearing at frequency $f$.

### Ideal Delta Target
The ideal loudness compensation curve $\Delta_{\text{ideal}}(f)$ is the difference in loudness contour shape between the target level $L$ and the reference level $L_{\text{ref}} = 83.0\text{ dB}$, normalized to 0 dB at 1000 Hz:

$$\Delta_{\text{ideal}}(f) = \left(L_p(L, f) - L_p(L, 1000)\right) - \left(L_p(83.0, f) - L_p(83.0, 1000)\right)$$

### Residual Error Calculation
The verification tool computes the cascaded PEQ response $R(f)$ using the biquad transfer functions and evaluates:

$$\text{Error}(f) = R(f) - \Delta_{\text{ideal}}(f)$$

The maximum residual error printed to the terminal is defined as:

$$\text{Max Residual Error} = \max_{f \in \text{Standard Frequencies}} \left| \text{Error}(f) \right|$$

---

## Generated Presets

Below are the pre-generated PEQ tables and frequency responses for the three primary listening scenarios. You can copy these settings directly into Roon's Parametric EQ processor.

### 1. Low Level (65 dB)
Designed for quiet, non-intrusive playback. See the generated [filter-65db.md](file:///home/dsnyder/src/iso-226/filter-65db.md) for details.

*   **Reference Level**: 83.0 dB
*   **Recommended Headroom Adjustment (Preamp Gain)**: `-9.16 dB`

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 35 | 1.35 | 0.71 |
| 2 | Low Shelf | 75 | 7.74 | 0.71 |
| 3 | Peak | 150 | 4.13 | 0.70 |
| 4 | Peak | 300 | 0.19 | 1.00 |
| 5 | Peak | 600 | 0.42 | 1.40 |
| 6 | Peak | 1000 | -0.57 | 1.00 |
| 7 | Peak | 3000 | -0.50 | 1.40 |
| 8 | Peak | 6000 | -1.09 | 1.00 |
| 9 | High Shelf | 10000 | 3.64 | 0.71 |
| 10 | High Shelf | 16000 | 4.73 | 0.71 |

![65 dB Frequency Response](images/filter-65db.png)

---

### 2. Medium Level (75 dB)
Designed for casual, extended listening sessions. See the generated [filter-75db.md](file:///home/dsnyder/src/iso-226/filter-75db.md) for details.

*   **Reference Level**: 83.0 dB
*   **Recommended Headroom Adjustment (Preamp Gain)**: `-4.78 dB`

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 35 | 0.66 | 0.71 |
| 2 | Low Shelf | 75 | 3.32 | 0.71 |
| 3 | Peak | 150 | 1.82 | 0.70 |
| 4 | Peak | 300 | 0.02 | 1.00 |
| 5 | Peak | 600 | 0.17 | 1.40 |
| 6 | Peak | 1000 | -0.33 | 1.00 |
| 7 | Peak | 3000 | -0.28 | 1.40 |
| 8 | Peak | 6000 | -0.49 | 1.00 |
| 9 | High Shelf | 10000 | 1.65 | 0.71 |
| 10 | High Shelf | 16000 | 3.02 | 0.71 |

![75 dB Frequency Response](images/filter-75db.png)

---

### 3. High Level (85 dB)
Designed for active demo sessions. Since this level is above the 83 dB reference, it applies only minor attenuation relative to the reference. See the generated [filter-85db.md](file:///home/dsnyder/src/iso-226/filter-85db.md) for details.

*   **Reference Level**: 83.0 dB
*   **Recommended Headroom Adjustment (Preamp Gain)**: `-0.09 dB`

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 35 | -0.17 | 0.71 |
| 2 | Low Shelf | 75 | -0.81 | 0.71 |
| 3 | Peak | 150 | -0.45 | 0.70 |
| 4 | Peak | 600 | -0.04 | 1.40 |
| 5 | Peak | 1000 | 0.10 | 1.00 |
| 6 | Peak | 3000 | 0.09 | 1.40 |
| 7 | Peak | 6000 | 0.12 | 1.00 |
| 8 | High Shelf | 10000 | -0.40 | 0.71 |
| 9 | High Shelf | 16000 | -1.00 | 0.71 |

![85 dB Frequency Response](images/filter-85db.png)
