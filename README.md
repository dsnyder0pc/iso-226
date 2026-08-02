# ISO 226 Equal-Loudness Compensation PEQ Generator

Generates parametric EQ (PEQ) filters that compensate for the way human hearing
changes with playback level, so that a recording keeps the tonal balance its
mastering engineer intended when you listen below the level it was mastered at.

The filters track the **ISO 226 equal-loudness contours**. A verification tool
checks the published filter values against the ideal contours and shows what the
optional refinement bands actually buy.

The equal-loudness arithmetic follows **ISO 226:2023** exactly — verified
against the standard's own Annex B contours to within 0.05 dB, that table's full
printed precision. Those values are ISO's and cannot be redistributed, so the
check ships disabled and is reproducible by anyone holding the standard; see
[Verification against the standard](#verification-against-the-standard). Applying it to music in a room requires
going past what the standard vouches for in three specific ways; those are
enumerated in
[Relationship to the standard](#relationship-to-the-standard) rather than glossed
over.

---

## Introduction & Context

Human hearing is not equally sensitive at all frequencies, and the shape of that
sensitivity changes with level: as playback gets quieter, bass and treble fall
away faster than the midrange. This is standardized in **ISO 226:2023**, the
current third edition.

Ideally a playback system would compensate dynamically, tracking the volume
control in real time. Achieving that inside ecosystems like **Roon** is
awkward, so this project takes the practical route: generate a small number of
static PEQ presets, one per listening level, and switch between them.

* **Quiet (~65 dB)** — late-night or background listening. Needs substantial
  bass lift and moderate treble lift.
* **Moderate (~75 dB)** — relaxed extended listening. Mild compensation.
* **Loud (~85 dB)** — active listening. Above the reference level, hearing is
  slightly *more* sensitive at the extremes, so the correction goes slightly
  negative.

This is a more principled version of the "loudness" switch found on vintage
receivers — a Pioneer SX-780, a Yamaha with its variable loudness control, a
Sansui — most of which applied a single fixed curve regardless of how loud you
were actually playing.

### Digital headroom & clipping

Equal-loudness compensation boosts the frequency extremes, so applied digitally
it can exceed `0 dBFS` and clip. There are two ways out:

1. **Cut the midrange instead of boosting the extremes.** Mathematically
   equivalent, and what the better vintage variable-loudness circuits did — it
   is also why they needed no preamp trim. Awkward to express as PEQ bands.
2. **Boost the extremes and apply a global preamp attenuation** equal to the
   peak of the combined response.

This project uses **option 2** and prints the exact attenuation to apply.

---

## Requirements

```bash
pip install -r requirements.txt
```

---

## Usage

### Generate filters

```bash
python loudness-filters.py --level <listening_db> [--reference <mastering_db>] [--scale <0.1-1.0>]
```

| Option | Default | Range | Meaning |
| :--- | :--- | :--- | :--- |
| `--level` | 65.0 | 50–90 | How loud it actually is in your room, **measured**. |
| `--reference` | 83.0 | 70–90 | How loud the recording was mastered to sound correct at. A property of the *recording*. |
| `--scale` | 1.0 | 0.1–1.0 | Fraction of the theoretical correction to apply. |

Keeping `--level` and `--reference` conceptually distinct matters. `--level` is
something you measure; `--reference` is something you know (or assume) about the
record. Confusing the two is what makes very quiet listening look impossible
when it isn't — see *Recordings mastered quietly* below.

Three files are written per preset, named
`filter_<reference>_to_<level>_s<scale>`: `.md` (the tables), `.yml`
(CamillaDSP YAML for REW import) and `.png` (the response plot). So the default
65 dB case produces `filter_83_to_65_s1.0.md` and friends. Both levels appear in
the name because a compensation curve is defined by the *pair*, not by the
listening level alone.

### Verify

```bash
python check.py --level <listening_db> [--reference <mastering_db>] [--scale <s>]
```

Reads the **published, rounded** filter values back out of the Markdown table,
compares them against the ideal ISO 226 target, prints the maximum residual
error for the essential five bands and for all ten, and saves
`filter_<reference>_to_<level>_s<scale>_error.png` showing both traces.

### Tests

```bash
python -m pytest tests/                  # everything
python -m pytest tests/ -m "not slow"    # skip the tests that run the optimizer
```

Most tests are fast. A handful are marked `slow` because they generate a real
preset (~30 s) and then assert the properties that actually ship: that bands
1–5 are exactly the first five of the ten, that no band exceeds the host's
±12 dB limit, that adjacent bands stay far enough apart, that the extrapolation
outside the ISO range stays bounded, and — the one that matters most — that the
published headroom figure really does keep the response at or below 0 dBFS at
every verified sample rate, for both the five-band and ten-band sets.

Two of these tests exist because the obvious way to verify this project does not
work.

`check.py` computes the ideal target with the same `iso226_spl` used to design
the filters, and evaluates the filters with the same `get_filter_response` used
to fit them. It therefore cannot detect an error in either routine — it can only
confirm that rounding and parsing are faithful. A low residual error printed by
`check.py` is not evidence that the math is right.

So the suite anchors on things the project does not compute itself:

* `test_matches_published_annex_b` checks Formula (1) against contour values
  published in **ISO 226:2023 Annex B, Table B.1**. See *Verification against
  the standard* below — this test ships disabled, because those values are
  ISO's.
* `test_high_shelf_passband_is_flat_at_every_rate` and
  `test_shelves_never_overshoot_their_own_gain` check the biquads against
  properties a shelving filter must have by definition — a cut may never produce
  a boost, and a high shelf must be 0 dB well below its corner.

That second group caught a real sign error in the `b2` coefficient of the
high-shelf formula that had been present since the project's first version. The
faulty term scaled with `cos(w0)`, so it was almost invisible at the sample rate
and corner frequency most often used, and grew from there. In the previously
shipped 65 dB preset it produced a **0.467 dB passband offset at 44.1 kHz, a
1.46 dB error at 14.2 kHz, and a 6.25 dB error at 96 kHz** — while `check.py`
reported a maximum residual error of 0.1185 dB, because it was measuring the
filters with the same broken function that built them.

---

## How to work out your `--level` — and why it is easier than it looks

`--level` is the one number you have to supply, and it is by far the largest
error source in the whole system. Getting it wrong by 6 dB shifts the correction
by about **3.15 dB**. Everything else here is argued over hundredths.

### The measurement convention does not have to be exact — only consistent

There is an apparent problem. ISO 226 defines *phon* as the level of a
frontally-incident **1 kHz pure tone** judged equally loud (ISO 226:2023 §3.3).
But nobody measures their listening room with a 1 kHz sine, and the 83 dB
reference convention doesn't either: Bob Katz's figure means broadband music,
measured at the listening position, **C-weighted, slow**.

That mismatch turns out not to matter, because the compensation is a
*difference* of two contours. If your measurement convention reads *k* dB away
from the true loudness level, both `--level` and `--reference` are shifted by
the same *k*, and it cancels to first order:

| Offset *k* | Worst residual error, 20 Hz – 12.5 kHz |
| :--- | :--- |
| 2 phon | 0.01 dB |
| 4 phon | 0.02 dB |
| 6 phon | 0.02 dB |
| 7 phon | 0.03 dB |

So **do not** try to measure a 1 kHz sine to derive `--level`. Doing so would
mix conventions between the two endpoints and *introduce* the error this
cancellation removes. Measure the way Katz did, and be consistent.

> This is verified by `test_measurement_convention_offset_cancels` and
> `test_level_error_matters_far_more_than_convention` in `tests/`.

### Method A — physical volume control and an SPL meter

The straightforward path, and the one that suits listening to an album at a
time:

1. Set the volume where you want it for this record.
2. Measure at the listening position: **C-weighted, slow**, averaged over about
   30 seconds of representative material. Use `Leq` (equivalent continuous
   level) if your meter or app offers it — you want an average, not a bouncing
   instantaneous reading and not a peak.
3. Use that number as `--level`.

Because you set the volume once per album, one measurement covers the sitting.

### Method B — Roon's digital volume, calibrated once

1. Enable **Volume Leveling in album mode**. Album mode, not track mode: track
   mode flattens the deliberate level differences *within* an album, which is
   exactly wrong if you listen to records end to end. A −18 LUFS target is a
   reasonable choice.
2. Calibrate once — play a leveled track, measure C-weighted slow at the
   listening position, and note the volume reading.
3. From then on, `--level` = calibrated SPL − however far you've turned it down.

Leveling is optional. Its real value is that it stabilizes the relationship
between volume setting and actual SPL *across* your library: without it,
mastering levels vary by 15 dB or more, so the same dial position produces
wildly different levels and no static preset can be right for long.

### How precise do you need to be?

Not very. Adjacent 5 dB presets differ by about **2.6 dB** of bass — clearly
audible, which is why 5 dB steps are the right granularity. Being within
±2–3 dB on `--level` is entirely good enough, and finer preset steps would not
be useful.

---

## Choosing filters: five bands or ten

Each generated preset contains ten bands in two groups:

* **Bands 1–5, "Essential"** — a complete, standalone, full-spectrum correction.
  Treble compensation is deliberately in this group, not deferred: at low levels
  the loss of perceived treble matters at least as much as the loss of bass,
  particularly for listeners with age-related high-frequency loss.
* **Bands 6–10, "Refinement"** — optional.

**The honest result: the refinement bands do essentially nothing.** Five
well-placed bands track the ISO 226 target to better than 0.07 dB, and the ISO
target is smooth enough that there is no structure left for five more bands to
correct. Their gains come out around 0.00–0.03 dB, which **rounds to 0.0 dB at
the 0.1 dB precision Roon accepts** — so typing them in by hand changes nothing
at all.

Across the shipped presets the second five change the worst-case error by under
0.007 dB — a fraction of Roon's 0.1 dB entry precision, and smaller than the
rounding on the numbers you would type. The figures below are measured on the
dense fitting grid; evaluated instead at the 29 ISO preferred frequencies (what
`check.py` reports and the error plots show) the two sets land within about
0.001 dB of each other and the ordering sometimes reverses, which is itself a
fair summary of how much the extra bands are worth:

| Preset | Bands 1–5 | All 10 |
| :--- | :--- | :--- |
| 62 dB | 0.0984 dB | 0.0864 dB |
| 65 dB | 0.0535 dB | 0.0506 dB |
| 70 dB | 0.0506 dB | 0.0436 dB |
| 75 dB | 0.0433 dB | 0.0432 dB |
| 80 dB | 0.0218 dB | 0.0197 dB |
| 85 dB | 0.0172 dB | 0.0159 dB |
| 90 dB | 0.0523 dB | 0.0421 dB |

The 62 dB preset is the loosest of the set, at 0.098 dB. That is expected: it
sits against the 12 dB gain ceiling, so the optimizer has less freedom than
elsewhere. It is still roughly two orders of magnitude below audibility.

They are kept because loading a YAML file costs nothing, and published so the
claim can be checked rather than taken on trust. The verification plot draws
both traces with the difference shaded, so you can see the size of what you
would be typing before deciding to type it.

For scale: the residual error either way is under 0.07 dB. In the listening test
discussed below, subjects had to repeat their own judgement within **±6 dB** to
qualify as consistent. This is what informed choice looks like — the plot is
there so you can decide, rather than adding filters because more feels better.

---

## Importing into REW, Roon and other DSPs

### Pre-generated filters (no Python required)

Ready-made CamillaDSP YAML files for an 83 dB mastering reference are in the
[REW](REW) directory:

| File | Listening level | Relative to reference |
| :--- | :--- | :--- |
| [filter_83_to_62_s1.0.yml](REW/filter_83_to_62_s1.0.yml) | 62 dB — very quiet | −21 dB |
| [filter_83_to_65_s1.0.yml](REW/filter_83_to_65_s1.0.yml) | 65 dB — quiet | −18 dB |
| [filter_83_to_70_s1.0.yml](REW/filter_83_to_70_s1.0.yml) | 70 dB | −13 dB |
| [filter_83_to_75_s1.0.yml](REW/filter_83_to_75_s1.0.yml) | 75 dB — moderate | −8 dB |
| [filter_83_to_80_s1.0.yml](REW/filter_83_to_80_s1.0.yml) | 80 dB | −3 dB |
| [filter_83_to_85_s1.0.yml](REW/filter_83_to_85_s1.0.yml) | 85 dB — loud | +2 dB |
| [filter_83_to_90_s1.0.yml](REW/filter_83_to_90_s1.0.yml) | 90 dB | +7 dB |

62 dB is the quietest preset possible at an 83 dB reference: below that the
correction needs more than the 12 dB Roon allows.

#### These files also work for other mastering references

The compensation curve depends almost entirely on the *difference* between the
two levels, not on the two levels separately. Across mastering references from
72 to 85 dB, curves sharing a difference agree to within 0.014 dB at −5,
0.034 dB at −10 and 0.104 dB at −20 — at worst 0.125 dB anywhere, which is
Roon's entry precision.

So each file above serves any reference at the same offset:

| File | −offset | ref 72 | ref 75 | ref 78 | ref 80 | ref 83 | ref 85 |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `..._to_62_...` | −21 | 51 | 54 | 57 | 59 | **62** | 64 |
| `..._to_65_...` | −18 | 54 | 57 | 60 | 62 | **65** | 67 |
| `..._to_70_...` | −13 | 59 | 62 | 65 | 67 | **70** | 72 |
| `..._to_75_...` | −8 | 64 | 67 | 70 | 72 | **75** | 77 |
| `..._to_80_...` | −3 | 69 | 72 | 75 | 77 | **80** | 82 |
| `..._to_85_...` | +2 | 74 | 77 | 80 | 82 | **85** | 87 |
| `..._to_90_...` | +7 | 79 | 82 | 85 | 87 | **90** | 92 |

Listening at 60 dB to something mastered for 78 dB? That is −18, so
`filter_83_to_65_s1.0.yml` is your file. If you would rather have one named for
your actual levels, generate it — `--reference 78 --level 60` takes half a
minute and writes `filter_78_to_60_s1.0.yml`.

### Loading into REW

1. Open **Room EQ Wizard** and choose **EQ**.
2. On the Equaliser tab select **CamillaDSP** as Manufacturer and **Filters** as
   Model.
3. Under **Filter Tasks** choose **Load filter settings from YAML file** and
   pick your `filter_<reference>_to_<level>_s<scale>.yml`.
4. You can then switch REW's Equaliser dropdown to another target device
   (miniDSP, Generic, …) and REW will translate the parameters to that device's
   limits.
5. **File > Export > Export filters impulse response as WAV** produces impulse
   responses for convolution engines (Roon Convolution, HQPlayer, JRiver).
   Choose the sample rate matching your library.

### Applying the headroom adjustment

Every generated file states a single headroom figure, for example `-9.5 dB`.
Enter it as a negative preamp gain (Roon's **Headroom Management**, Equalizer
APO's preamp, or your hardware DSP's input gain).

That figure is:

* the **worst case across 44.1 / 48 / 96 / 192 kHz** (see below),
* valid for **either** the essential five bands or all ten, and
* rounded away from zero to 0.1 dB, the precision Roon accepts.

### Gain limits on real hardware

Roon's MUSE Parametric EQ gain control spans **+12 to −12 dB**. miniDSP allows
±16 dB. The generator therefore caps both individual band gains and the total
required attenuation at **12 dB**, which satisfies both platforms.

This creates a real floor. At an 83 dB reference, full compensation needs more
than 12 dB below roughly **62 dB SPL** — so 55 and 60 dB presets referenced to
83 dB cannot be built, and none are shipped. If you ask for one, the generator
refuses and suggests a `--scale` value and a `--level` that would fit:

```
Error: Cannot build a usable filter set for --level 50 --reference 83: the
required headroom (-21.08 dB) exceeds the 12.0 dB available on Roon's
Parametric EQ gain control.
  (largest single band gain in this fit: 12.00 dB)

Try one of:
  --scale 0.65      apply partial compensation (about 65% of the theoretical curve)
  --level 62       target a higher listening level
  --reference <lower>  if this recording is mastered quieter than 83 dB
```

If your DSP can attenuate beyond −12 dB (Roon's Headroom Management is a
separate control from the PEQ gain slider), you can route the excess there.

### Recordings mastered quietly

Some recordings are voiced for a much lower playback level. Jay Stocker's
*[Scripture Lullabies](https://scripture-lullabies.com/pages/stream)* series,
designed for bedtime listening, is a good example. For those, lower
`--reference` rather than fighting the level:

```bash
python loudness-filters.py --level 55 --reference 72
```

That builds cleanly (headroom −8.9 dB), where `--level 55 --reference 83` cannot.
This is why very quiet listening levels remain valid options even though no
pre-generated 83 dB-referenced presets exist for them.

---

## Generated Presets

The essential five bands for the three headline levels, all referenced to
83 dB. These are the values to type into Roon's Parametric EQ. The optional
refinement bands are in the generated `.md` tables and in the YAML files; as discussed above, they round to 0.0 dB at Roon's entry precision.

### Quiet — 65 dB

**Headroom adjustment `-9.5 dB`** · max residual error **0.0535 dB**

| Band | Type | Frequency (Hz) | Gain (dB) | Q |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 66.7 | +10.51 | 0.44 |
| 2 | Peak | 301.9 | +3.06 | 0.25 |
| 3 | Peak | 588.8 | −1.95 | 0.43 |
| 4 | Peak | 3523.8 | −0.83 | 0.25 |
| 5 | High Shelf | 10173.1 | +3.79 | 0.71 |

![65 dB frequency response](images/filter_83_to_65_s1.0.png)
![65 dB residual error](images/filter_83_to_65_s1.0_error.png)

### Moderate — 75 dB

**Headroom adjustment `-4.2 dB`** · max residual error **0.0433 dB**

| Band | Type | Frequency (Hz) | Gain (dB) | Q |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 120.0 | +4.53 | 0.34 |
| 2 | Peak | 450.0 | −0.32 | 0.48 |
| 3 | Peak | 1599.4 | +0.53 | 0.25 |
| 4 | Peak | 3607.5 | −0.89 | 0.25 |
| 5 | High Shelf | 10373.3 | +2.19 | 0.56 |

![75 dB frequency response](images/filter_83_to_75_s1.0.png)
![75 dB residual error](images/filter_83_to_75_s1.0_error.png)

### Loud — 85 dB

Above the 83 dB reference, so the correction is a slight *cut* at the extremes.

**Headroom adjustment `-0.1 dB`** · max residual error **0.0172 dB**

| Band | Type | Frequency (Hz) | Gain (dB) | Q |
| :--- | :--- | :--- | :--- | :--- |
| 1 | Low Shelf | 39.3 | −1.75 | 0.26 |
| 2 | Peak | 280.2 | −0.12 | 0.66 |
| 3 | Peak | 927.0 | +0.01 | 0.39 |
| 4 | Peak | 2910.3 | +0.07 | 0.40 |
| 5 | High Shelf | 9868.3 | −0.32 | 0.88 |

![85 dB frequency response](images/filter_83_to_85_s1.0.png)
![85 dB residual error](images/filter_83_to_85_s1.0_error.png)

---

## The Math Behind It

### Relationship to the standard

This project implements **ISO 226:2023**, the current third edition. The
distinction worth drawing is between the arithmetic and its application:

* **The arithmetic is faithful.** Formula (1) and the Table 1 coefficients are
  implemented as published, and the result has been verified to within
  **0.05 dB** of the 40 phon contour in ISO 226:2023 Annex B, Table B.1 — exact
  agreement at that table's printed precision. See *Verification against the
  standard* below for how to reproduce it.
* **The application deliberately goes past what the standard vouches for**, in
  three documented places, each because the practical problem requires it:
  1. The 83 dB mastering reference exceeds the 80 phon ceiling above 5 kHz.
  2. Compensation is extended above 12.5 kHz and below 20 Hz, where the
     standard has no data at all.
  3. The contours describe pure tones auditioned in a free field by listeners
     aged 18–25; they are applied here to broadband music in a room.

Each is detailed below, with its magnitude where that can be established.

None of this is unusual for applied loudness compensation. Every commercial
implementation — Audyssey Dynamic EQ, THX Loudness Plus, the vintage
variable-loudness circuits — makes the same jump from pure-tone contours to
music. The difference is only that the departures are enumerated here instead of
left implicit.

#### On reproducing ISO's data

Two pieces of ISO 226:2023 appear in this repository, and they are treated
differently on purpose.

**Table 1** — the 29 rows of $\alpha_f$, $L_U$ and $T_f$ — is reproduced in
`iso226_utils.py`. It has to be: those 87 numbers *are* the standard's model of
hearing, and without them there is no working implementation to publish. They
are measured and fitted parameters rather than creative expression, and the
equivalent table from the 2003 edition has been reproduced openly in numerous
public implementations for two decades. They are reproduced here in that spirit,
with attribution, and this project is not a substitute for the standard: anyone
doing serious work with equal-loudness contours should buy it.

**Annex B** is not reproduced. It is the one piece that is genuinely
paywall-exclusive, it is not needed to *run* anything, and it is used only to
check the implementation — so it is supplied locally by whoever owns a copy.

The software is MIT licensed (see `LICENSE`). That licence covers the code, not
ISO's coefficients, which are not mine to sub-license — see `NOTICE`. ISO
confirmed on 1 August 2026 that reproducing Table 1 requires explicit
permission, and a request is currently with ANSI, the US member body. If it is
refused the coefficients will be removed and `NOTICE` updated accordingly.

Note that ISO's own free preview does **not** include Table 1; it covers the
Foreword, Introduction, Scope, normative references and terms only. The
coefficients are also visible in the ISO/PRF 226 draft preview redistributed by
iTeh Standards, but that is a third-party reseller's copy of official ISO
material, not an ISO-hosted free release, and it is cited here as a convenience
rather than as a licence.

#### Verification against the standard

The implementation here has been **checked against ISO 226:2023 Annex B,
Table B.1 — the standard's own published contours — and agrees to within
0.05 dB**, which is the full printed precision of that table. The check covers
the 40 phon contour across all 29 ISO 266 preferred frequencies from 20 Hz to
12.5 kHz.

That verification is not something you can take on trust from this file, and it
is also not something this repository can hand you. Annex B is behind ISO's
paywall and is licensed single-user; its values are therefore **not included
here**. The test that performs the check (`test_matches_published_annex_b`)
ships disabled and skips with an explanatory message.

If you own a copy of ISO 226:2023, you can re-run the verification yourself in
about two minutes: copy `tests/annex_b_reference.py.example` to
`reference/annex_b_2023.py`, type in the 40 phon row of Table B.1, and run
`pytest`. Nothing else changes. Everyone else gets a suite that still exercises
the biquad identities, the target construction and the generator — just not the
one assertion that depends on ISO's data.

This matters more than it might appear. `check.py` computes its ideal target and
evaluates its filters with the very functions it is checking, so a low residual
error there proves nothing about whether the math is right. Annex B is the only
external anchor in the project — the single point where the implementation is
measured against something it did not produce.

> **On the 2003 edition.** ISO 226:2003 is superseded and is not used here.
> The two editions are not interchangeable: the third edition restructured
> Formula (1) and changed **every** $\alpha_f$ in Table 1, because the loudness
> exponent at 1 kHz was revised from 0.25 to 0.30. A claim circulates that only
> the 20 Hz hearing threshold changed; that is incorrect. The resulting contours
> differ by up to 0.6 dB, which for a *difference* of two contours works out at
> under 0.25 dB on the compensation curves here — so the move to 2023 is a
> correctness and citation decision, not an audible one.

### ISO 226 equal-loudness contours

The sound pressure level $L_f$ of a pure tone of frequency $f$ having loudness
level $L_N$, per **ISO 226:2023 Formula (1)**:

$$L_f = \frac{10}{\alpha_f} \log_{10}\left(A_f\right) - L_U$$

$$A_f = \left(\frac{p_0}{p_a}\right)^{2(\alpha_r - \alpha_f)} \left(10^{\frac{\alpha_r L_N}{10}} - 10^{\frac{\alpha_r T_r}{10}}\right) + 10^{\frac{\alpha_f (T_f + L_U)}{10}}$$

where $\alpha_f$, $L_U$ and $T_f$ are the per-frequency coefficients of
ISO 226:2023 Table 1; $\alpha_r = 0.30$ and $T_r = 2.4$ dB are the loudness
exponent and hearing threshold at 1 kHz; and $p_0 = 20\,\mu\text{Pa}$, so
$(p_0/p_a)^2 = 4 \times 10^{-10}$.

The structure is easier to read than the 2003 equation once you see what it
says. The bracketed difference is the loudness of the 1 kHz reference tone above
its own threshold; the trailing term is the threshold at frequency $f$. Setting
them equal is the definition of an equal-loudness contour. The pressure factor
reconciles the two different exponents and is exactly unity at 1 kHz, where
$\alpha_f = \alpha_r = 0.30$ — which is also why a contour at $L_N$ phon passes
through exactly $L_N$ dB at 1 kHz.

Coefficients are interpolated in **log** frequency, the axis they are tabulated
on.

### The compensation target

$$\Delta(f) = \left(L_p(L, f) - L_p(L, 1000)\right) - \left(L_p(L_{\text{ref}}, f) - L_p(L_{\text{ref}}, 1000)\right)$$

normalized to 0 dB at 1 kHz, then multiplied by `--scale`.

### Fitting

Filters are fitted by **minimax** — minimizing the largest absolute deviation
rather than the sum of squares — because what matters is the worst error across
the band, not the average.

The problem is solved in **epigraph form**: minimize $t$ subject to
$|\text{error}| \le t$. Handing $\max|\text{error}|$ directly to a gradient
optimizer does not work well; that function is not differentiable exactly at the
optimum, where the solver spends its time. Reformulating it as a smooth
constrained problem improves the fit roughly three- to fivefold for the same
filter topology.

Two further constraints keep the result physically sensible:

* **Per-band gain is bounded to ±12 dB**, and **total absolute gain is
  budgeted.** Without these, a minimax fit will happily place two large,
  nearly-cancelling filters at almost the same frequency (e.g. +17.33 dB at
  396 Hz against −16.12 dB at 438 Hz). The end-to-end magnitude response is
  fine, and since RBJ biquads are minimum-phase the phase cancels too — there is
  no pre-ringing, which is a linear-phase FIR artifact. The damage is elsewhere:
  a serial fixed-point chain can overflow an intermediate node while the overall
  response looks clean, and rounding no longer cancels between two large
  opposing filters, so host coefficient quantization produces a large net error.
  Frequency ranges within a tier are also non-overlapping.
* **Out-of-band deviation is bounded** but not optimized (below).

The generator reports cascade conditioning — the worst intermediate stage gain
and a quantization-sensitivity figure — so these properties can be checked
rather than assumed.

### Designed at 44.1 kHz

A biquad is designed in the digital domain, so the bilinear transform warps its
shape as the corner frequency approaches Nyquist. The same `(frequency, gain,
Q)` triple therefore realizes a slightly different response at 44.1 kHz than at
192 kHz — REW, Roon and miniDSP each rebuild the coefficients at whatever rate
they are running.

Filters are designed and analysed at **44.1 kHz**, still by far the most common
rate for digital music, and headroom is then verified at 44.1, 48, 96 and
192 kHz with the worst case published.

The effect is confined to the top octave, and 44.1 kHz is the conservative
choice there. Evaluating the previous version's filter set with correct biquad
math gives a peak gain of +9.16 dB at *every* rate — the peak lives in the bass,
where warping is negligible — while its response at 20 kHz ranges from
**+8.44 dB at 44.1 kHz down to +6.32 dB at 192 kHz**. Designing at the rate that
produces the most high-frequency gain means the published headroom is never
optimistic.

> An earlier draft of this section claimed the spread was much larger, with a
> peak of +12.73 dB at 192 kHz. That was an artifact of the high-shelf
> coefficient bug described under *Tests* above, not a real sample-rate effect.
> It is recorded here because it is a good illustration of how a bug in shared
> math contaminates every conclusion drawn from it.

### Where the standard stops, and what we do past it

ISO 226:2023 §4.1 states that Formula (1) applies from a lower limit of
20 phon up to (the limits are unchanged from the 2003 edition):

> **20 Hz to 4 000 Hz: 90 phon**
> **5 000 Hz to 12 500 Hz: 80 phon**

Note that the ceiling is not rectangular: it drops from 90 phon to 80 phon above
5 kHz, because that is where the underlying listening-test data thins out. The
equation does not misbehave outside its declared domain — it returns smooth,
plausible values with nothing to signal that you have left the evidence behind.
That is exactly what makes it easy to overrun without noticing.

Two honest disclosures follow:

1. **The default 83 dB reference sits above the 80 phon ceiling for 5–12.5 kHz.**
   Because the correction is `contour(level) − contour(83)`, the reference term
   appears in *every* preset, so this affects the high-frequency portion of the
   whole ladder — and for the 85 and 90 dB presets the target contour is beyond
   the ceiling up there as well.

   **How wrong is it? That is not measurable from here**, and no honest number
   can be quoted: establishing the extrapolation error would require exactly the
   data ISO says it does not have. What *can* be measured is how much the region
   is worth at all. Shifting the reference from 83 to 80 phon — a genuinely
   different mastering level, not a compliance correction — moves the 65 dB
   result by 0.21 dB at 10 kHz and 0.45 dB at 12.5 kHz. So the whole band is
   worth a few tenths of a dB, and even a substantial extrapolation error stays
   small in absolute terms.

   We do not clamp the reference to 80 phon to comply. 83 dB is the level at
   which this music is actually mastered; forcing it to 80 would deliberately
   mis-model the recording in order to tidy up the citation.
2. **There is no ISO data below 20 Hz or above 12.5 kHz at all.** Rather than
   let the fit do whatever it likes there, the target is **held flat** at the
   edge value from 10 Hz to 20 Hz and from 12.5 kHz to 20 kHz, and deviation in
   those regions is constrained to ±1.5 dB without contributing to the
   objective. The extrapolation is therefore bounded and deliberate.

For the 65 dB preset this produces:

| Frequency | Previous version | Now |
| :--- | :--- | :--- |
| 2 Hz | +9.87 dB | +10.50 dB |
| 20 Hz *(last ISO data point)* | +9.37 dB | +9.44 dB |
| 20 kHz | +8.29 dB | +3.78 dB |

The high-frequency extrapolation is much better behaved — the old 16 kHz shelf
was still climbing at 20 kHz, where there is no data and little hearing.

**The subsonic region is not improved, and it is worth being clear about that.**
A low shelf must asymptote to its full gain eventually, so a preset that lifts
20 Hz by 9.4 dB will apply roughly that much below 20 Hz too. The constraint
guarantees it stays *bounded* near the 20 Hz value instead of running away, but
it cannot make it disappear. If you play material with significant subsonic
content — vinyl rips, warped records, badly filtered transfers — **add a
high-pass filter at 15–20 Hz ahead of these filters.** That is a separate
measure this project does not attempt, and at these gains it is worth having.

Note also that 12.5 kHz to 20 kHz is barely more than half an octave of the
audible range, and many listeners in the target audience for loudness
compensation have little hearing left above 12.5 kHz.

---

## Honest limitations

* **ISO 226 describes pure tones, not music.** The standard's own Scope
  specifies a free progressive plane wave, a source directly in front of the
  listener, pure tones, binaural listening, and listeners aged 18–25. A living
  room with a stereo pair playing broadband music satisfies none of the first
  four, and few audiophiles satisfy the fifth. ISO's Note 1 does allow that the
  standard "could be applicable to one-third-octave-bands of noise."
* **Deriving a compensation curve by differencing pure-tone contours is a
  known approximation.** Loudness sums across critical bands in ways pure-tone
  contours do not capture, and the patent literature contains the blunt claim
  that equal-loudness contours "are not the proper curves to use in the design
  of a loudness control." The counter-evidence is empirical and reassuring: the
  Fierro/Rämö/Välimäki listening test found that contour-derived compensation
  "can reproduce the average response of the listeners" on real music.
* **The precision here vastly exceeds the accuracy of the underlying
  perception.** In that same test, qualifying as a *consistent* listener
  required repeating your own bass-balance judgement within ±6 dB at 80 dB SPL
  and ±10 dB at 60 dB SPL, and 7 of 18 subjects failed even that. A fit error of
  0.07 dB is not the limiting factor in whether this sounds right.
* **`--scale` is a taste control, not an error correction.** If full
  compensation sounds like too much, use less. That is a legitimate preference,
  not a defect in the math.

---

## References

* **ISO 226:2023**, *Acoustics — Normal equal-loudness-level contours*, third
  edition — **the edition implemented here**. Scope, §3.3 (definition of phon),
  §4.1 (Formula (1) and its stated range of validity), Table 1 (coefficients),
  Annex B Table B.1 (published contours, used as this project's external
  regression anchor).
  [ISO 226:2023](https://www.iso.org/standard/83117.html).
  ISO's own free preview (the Online Browsing Platform) covers only the
  Foreword, Introduction, Scope, normative references and terms — **not**
  clause 4 or Table 1. The same content is visible in the ISO/PRF 226 draft
  preview redistributed by iTeh Standards, a commercial standards reseller:
  [ISO/PRF 226 preview](https://cdn.standards.iteh.ai/samples/83117/7d18fe0f9ae04beaa6f5567980201e7f/ISO-PRF-226.pdf).
  That document is official ISO material (© ISO 2023) hosted by a third party,
  not by ISO. Annex B appears in neither preview.
* **ISO 226:2003**, second edition — superseded, and *not* used here. Retained
  as a reference only because much published work still assumes it.
  [ISO 226:2003](https://www.iso.org/standard/34222.html)
* **ISO 226:2023**, third edition. Restructures Formula (1), revises every
  $\alpha_f$ in Table 1 (the 1 kHz loudness exponent moves from 0.25 to 0.30),
  and aligns the 20 Hz threshold with ISO 389-7:2019. Its §4.1 validity limits
  are **identical** to the 2003 edition's. Annexes A–C become informative.
  [ISO 226:2023](https://www.iso.org/standard/83117.html) ·
  [ISO/PRF 226 draft preview](https://cdn.standards.iteh.ai/samples/83117/7d18fe0f9ae04beaa6f5567980201e7f/ISO-PRF-226.pdf)
  (official ISO draft material, redistributed by the reseller iTeh Standards —
  not an ISO-hosted document).
* **Suzuki, Y., Takeshima, H., & Kurakata, K. (2024).** *Revision of ISO 226
  "Normal Equal-Loudness-Level Contours" from 2003 to 2023 edition: The
  background and results.* Acoust. Sci. & Tech. 45(1). Open access (CC BY-ND),
  by the authors of the revision. Quantifies the difference between editions
  (−0.6 to +0.3 dB; within ±0.3 dB above 10 phon) and states that the 2023
  $\alpha_f$ values are identical to those of the JASA 2004 paper.
  [J-Stage](https://www.jstage.jst.go.jp/article/ast/45/1/45_e23.66/_article)
* **Fierro, L., Rämö, J., & Välimäki, V. (2019).** *Adaptive Loudness
  Compensation in Music Listening.* Proc. 16th Sound and Music Computing
  Conference (SMC-19), Málaga. Derives the same contour-difference target,
  implements it as a first-order shelving filter, and validates it with a formal
  listening test.
  [PDF](https://www.smc2019.uma.es/articles/S2/S2_01_SMC2019_paper.pdf)
* **Katz, R.** *Mastering Audio: The Art and the Science.* Source of the 83 dB
  SPL monitoring convention (the K-System), and of the 80–85 dB range within
  which most popular music is mastered.
* **Bristow-Johnson, R.** *Cookbook formulae for audio EQ biquad filter
  coefficients.*
  [Audio EQ Cookbook](https://webaudio.github.io/Audio-EQ-Cookbook/audio-eq-cookbook.html)
* **Audyssey Dynamic EQ** — commercial ISO 226-derived loudness compensation
  referenced to film reference level; its Reference Level Offset is the same
  idea as `--reference`, in coarse 5 dB steps.
  [Dynamic EQ and Reference Level](https://ask.audyssey.com/hc/en-us/articles/212347383-Dynamic-EQ-and-Reference-Level)
* **ITU-R BS.1770** / **EBU R128** — loudness measurement underlying LUFS-based
  volume leveling.
* **Room EQ Wizard documentation.**
  [REW Help](https://www.roomeqwizard.com/help/help/html/eqwindow.html)
* **Roon Labs Knowledge Base** — DSP engine, Parametric EQ and Headroom
  Management.
  [Roon Help](https://help.roonlabs.com/portal/en/kb/articles/dsp-engine)
* **Equalizer APO documentation.**
  [Equalizer APO](https://sourceforge.net/p/equalizerapo/wiki/Documentation/)
