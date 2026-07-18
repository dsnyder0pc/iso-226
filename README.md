# ISO 226 Equal-Loudness Compensation PEQ Generator

This repository provides a utility to generate Parametric EQ (PEQ) filters that compensate for the human ear's frequency response variation at different playback levels. The filters track the **ISO 226 equal-loudness contours** relative to a reference level of 83 dB SPL (Sound Pressure Level) to ensure a consistent perceived tonal balance at any volume.

---

## Introduction & Context

The human ear does not perceive all frequencies equally. Crucially, our sensitivity to bass (low frequencies) and treble (high frequencies) drops significantly as the overall volume level decreases. This phenomenon is standardized in **ISO 226**.

To maintain a natural and consistent tonal balance, audio playback systems ideally need dynamic loudness compensation—where EQ curves dynamically adjust based on the current volume level. However, achieving real-time feedback from a volume control or room SPL meter in playback ecosystems like **Roon** is technically challenging.

This project solves that problem by generating three distinct static PEQ presets for common listening levels:

*   **Low (~62 dB)**: Used for quiet listening (e.g., when family members are watching TV in adjacent rooms). Needs significant bass and treble boost.
*   **Medium (~75 dB)**: Used for casual longer listening sessions (e.g., weekend background music). Needs mild bass and treble compensation.
*   **High (~87 dB)**: Used for active demo/loud listening sessions. At levels above 83 dB, human hearing becomes slightly more sensitive to low/high frequencies, requiring minor attenuation (negative gain) relative to the flat reference.

This approach offers a practical, high-fidelity alternative to the classic "one-size-fits-all" loudness switches found on vintage receivers (like the Pioneer SX-780 driving Pioneer HPM 100 speakers), which were either on or off and not level-aware.

### Digital Headroom & Clipping Prevention
Because equal-loudness compensation requires boosts in the low and high frequencies, applying these filters digitally can exceed `0 dB` and cause digital clipping (distortion). To prevent this, there are two primary methods:
1.  **Midrange Attenuation (Only Cuts)**: Designing filters that only cut the mids (similar to how vintage Yamaha variable loudness circuits behave). While mathematically equivalent, this is complex to configure as PEQ bands.
2.  **Loudness Boosts + Preamp Attenuation**: Keeping the intuitive boosting filters (low/high shelves) and applying a global preamp reduction (headroom adjustment) equal to the highest peak of the combined filter response. This is the industry-standard method for DSP systems like Roon or miniDSP.

This project implements **Option 2**. The generator calculates the exact peak gain of the combined response and outputs the recommended negative preamp offset to ensure the entire filter curve remains at or below `0 dB`.

---

## How It Works

The script [loudness-filters.py](file:///home/dsnyder/src/iso-226/loudness-filters.py) calculates the required EQ corrections based on a baseline EQ profile designed for a 65 dB target level (representing an 18 dB deviation from the 83 dB reference level).

1.  **Scaling**: Scales the baseline gains in [BASE_FILTERS](file:///home/dsnyder/src/iso-226/loudness-filters.py#L22) proportionally based on the target level's distance from the 83 dB reference level.
2.  **Biquad Calculation**: Using Robert Bristow-Johnson's Audio EQ Cookbook formulas implemented in [get_biquad_coefs](file:///home/dsnyder/src/iso-226/loudness-filters.py#L36), it designs digital biquad filter coefficients for low-shelf, high-shelf, and peak filters.
3.  **Headroom Calculation**: Evaluates the combined response and computes the required negative headroom offset in [calculate_headroom_offset](file:///home/dsnyder/src/iso-226/loudness-filters.py#L83) to keep peak gain below 0 dB.
4.  **Visualization**: Evaluates and plots the combined frequency response (including the headroom adjustment) relative to the 0 dB clipping ceiling in [plot_frequency_response](file:///home/dsnyder/src/iso-226/loudness-filters.py#L122).
5.  **Tables**: Outputs a formatted Markdown table detailing the PEQ bands and the required headroom adjustment offset using [write_markdown_table](file:///home/dsnyder/src/iso-226/loudness-filters.py#L101).

---

## Requirements

Ensure you have Python 3 and the dependencies listed in [requirements.txt](file:///home/dsnyder/src/iso-226/requirements.txt) installed:

```bash
pip install -r requirements.txt
```

---

## Usage

Run the generator script by specifying your target average listening level in dB:

```bash
python loudness-filters.py --level <target_db>
```

### Command-Line Arguments
*   `--level` (float, default: `65.0`): The target average room sound pressure level (SPL) in dB.

---

## Generated Presets

Below are the pre-generated PEQ tables and frequency responses for the three primary listening scenarios. You can copy these settings directly into Roon's Parametric EQ processor.

### 1. Low Level (62 dB)
Designed for quiet, non-intrusive playback. See the generated [filter-62db.md](file:///home/dsnyder/src/iso-226/filter-62db.md) for raw details.

*   **Reference Level**: 83.0 dB
*   **Recommended Headroom Adjustment (Preamp Gain)**: `-5.61 dB`

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 35 | 2.92 | 0.71 |
| 2 | Low Shelf | 75 | 2.92 | 0.71 |
| 3 | Peak | 150 | 1.17 | 0.70 |
| 4 | Peak | 300 | 0.58 | 1.00 |
| 5 | Peak | 600 | 0.23 | 1.40 |
| 6 | Peak | 3000 | 0.23 | 1.40 |
| 7 | Peak | 6000 | 0.58 | 1.00 |
| 8 | High Shelf | 10000 | 0.93 | 0.71 |
| 9 | High Shelf | 16000 | 1.17 | 0.71 |

![62 dB Frequency Response](filter-62db.png)

---

### 2. Medium Level (75 dB)
Designed for casual, extended listening sessions. See the generated [filter-75db.md](file:///home/dsnyder/src/iso-226/filter-75db.md) for raw details.

*   **Reference Level**: 83.0 dB
*   **Recommended Headroom Adjustment (Preamp Gain)**: `-2.13 dB`

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 35 | 1.11 | 0.71 |
| 2 | Low Shelf | 75 | 1.11 | 0.71 |
| 3 | Peak | 150 | 0.44 | 0.70 |
| 4 | Peak | 300 | 0.22 | 1.00 |
| 5 | Peak | 600 | 0.09 | 1.40 |
| 6 | Peak | 3000 | 0.09 | 1.40 |
| 7 | Peak | 6000 | 0.22 | 1.00 |
| 8 | High Shelf | 10000 | 0.36 | 0.71 |
| 9 | High Shelf | 16000 | 0.44 | 0.71 |

![75 dB Frequency Response](filter-75db.png)

---

### 3. High Level (87 dB)
Designed for active demo sessions. Since this level is above the 83 dB reference, it applies only attenuation (cuts). No headroom adjustment is required. See the generated [filter-87db.md](file:///home/dsnyder/src/iso-226/filter-87db.md) for raw details.

*   **Reference Level**: 83.0 dB
*   **Recommended Headroom Adjustment (Preamp Gain)**: `0.00 dB`

| Band | Type | Center Frequency (Hz) | Amplitude (dB) | Q-Value |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 35 | -0.56 | 0.71 |
| 2 | Low Shelf | 75 | -0.56 | 0.71 |
| 3 | Peak | 150 | -0.22 | 0.70 |
| 4 | Peak | 300 | -0.11 | 1.00 |
| 5 | Peak | 600 | -0.04 | 1.40 |
| 6 | Peak | 3000 | -0.04 | 1.40 |
| 7 | Peak | 6000 | -0.11 | 1.00 |
| 8 | High Shelf | 10000 | -0.18 | 0.71 |
| 9 | High Shelf | 16000 | -0.22 | 0.71 |

![87 dB Frequency Response](filter-87db.png)
