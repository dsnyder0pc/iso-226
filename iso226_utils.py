"""
ISO 226 equal-loudness contours and biquad filter calculation helper.
"""

import numpy as np
from scipy.signal import freqz

# ISO 226:2023 Standard Coefficients for Preferred Frequencies
ISO_FREQ = np.array([
    20.0, 25.0, 31.5, 40.0, 50.0, 63.0, 80.0, 100.0, 125.0, 160.0, 200.0,
    250.0, 315.0, 400.0, 500.0, 630.0, 800.0, 1000.0, 1250.0, 1600.0,
    2000.0, 2500.0, 3150.0, 4000.0, 5000.0, 6300.0, 8000.0, 10000.0, 12500.0
])

ISO_AF = np.array([
    0.635, 0.602, 0.569, 0.537, 0.509, 0.482, 0.456, 0.433, 0.412, 0.391,
    0.373, 0.357, 0.343, 0.330, 0.320, 0.311, 0.303, 0.300, 0.295, 0.292,
    0.290, 0.290, 0.289, 0.289, 0.289, 0.293, 0.303, 0.323, 0.354
])

ISO_LU = np.array([
    -31.6, -27.2, -23.0, -19.1, -15.9, -13.0, -10.3, -8.1, -6.2, -4.5,
    -3.1, -2.0, -1.1, -0.4, 0.0, 0.3, 0.5, 0.0, -2.7, -4.1,
    -1.0, 1.7, 2.5, 1.2, -2.1, -7.1, -11.2, -10.7, -3.1
])

ISO_TF = np.array([
    78.1, 68.7, 59.5, 51.1, 44.0, 37.5, 31.5, 26.5, 22.1, 17.9,
    14.4, 11.4, 8.6, 6.2, 4.4, 3.0, 2.2, 2.4, 3.5, 1.7,
    -1.3, -4.2, -6.0, -5.4, -1.5, 6.0, 12.6, 13.9, 12.3
])


def iso226_spl(phon, f_arr=None):
    """Calculates Sound Pressure Level (dB SPL) for a given phon level per ISO 226:2023.

    Args:
        phon (float): Phon level.
        f_arr (np.ndarray): Frequencies to calculate for. Defaults to ISO_FREQ.

    Returns:
        np.ndarray: Sound Pressure Level array.
    """
    if f_arr is None:
        f_arr = ISO_FREQ
    af = np.interp(f_arr, ISO_FREQ, ISO_AF)
    lu = np.interp(f_arr, ISO_FREQ, ISO_LU)
    tf = np.interp(f_arr, ISO_FREQ, ISO_TF)

    # Official ISO 226:2023 standard formula
    a_f = (4e-10)**(0.3 - af) * (10**(0.03 * phon) - 10**0.072) + 10**(af * (tf + lu) / 10.0)
    l_p = (10.0 / af) * np.log10(a_f) - lu
    return l_p


def get_biquad_coefs(ftype, fc, fs, gain, q):
    """Generates biquad coefficients based on Robert Bristow-Johnson's Audio EQ Cookbook.

    Args:
        ftype (str): Filter type, one of 'Peak', 'Low Shelf', or 'High Shelf'.
        fc (float): Center frequency in Hz.
        fs (float): Sampling frequency in Hz.
        gain (float): Gain in dB.
        q (float): Q-factor.

    Returns:
        tuple: lists of feedforward (b) and feedback (a) coefficients.
    """
    a_val = 10 ** (gain / 40.0)
    w0 = 2 * np.pi * fc / fs
    alpha = np.sin(w0) / (2 * q)

    if gain == 0:
        return [1.0, 0.0, 0.0], [1.0, 0.0, 0.0]

    b0, b1, b2 = 0.0, 0.0, 0.0
    a0, a1, a2 = 1.0, 0.0, 0.0

    if ftype == 'Peak':
        b0 = 1 + alpha * a_val
        b1 = -2 * np.cos(w0)
        b2 = 1 - alpha * a_val
        a0 = 1 + alpha / a_val
        a1 = -2 * np.cos(w0)
        a2 = 1 - alpha / a_val
    elif ftype == 'Low Shelf':
        b0 = a_val * ((a_val + 1) - (a_val - 1) * np.cos(w0) + 2 * np.sqrt(a_val) * alpha)
        b1 = 2 * a_val * ((a_val - 1) - (a_val + 1) * np.cos(w0))
        b2 = a_val * ((a_val + 1) - (a_val - 1) * np.cos(w0) - 2 * np.sqrt(a_val) * alpha)
        a0 = (a_val + 1) + (a_val - 1) * np.cos(w0) + 2 * np.sqrt(a_val) * alpha
        a1 = -2 * ((a_val - 1) + (a_val + 1) * np.cos(w0))
        a2 = (a_val + 1) + (a_val - 1) * np.cos(w0) - 2 * np.sqrt(a_val) * alpha
    elif ftype == 'High Shelf':
        b0 = a_val * ((a_val + 1) + (a_val - 1) * np.cos(w0) + 2 * np.sqrt(a_val) * alpha)
        b1 = -2 * a_val * ((a_val - 1) + (a_val + 1) * np.cos(w0))
        b2 = a_val * ((a_val + 1) - (a_val - 1) * np.cos(w0) - 2 * np.sqrt(a_val) * alpha)
        a0 = (a_val + 1) - (a_val - 1) * np.cos(w0) + 2 * np.sqrt(a_val) * alpha
        a1 = 2 * ((a_val - 1) - (a_val + 1) * np.cos(w0))
        a2 = (a_val + 1) - (a_val - 1) * np.cos(w0) - 2 * np.sqrt(a_val) * alpha
    else:
        raise ValueError(f"Unsupported filter type: {ftype}")

    return [b0 / a0, b1 / a0, b2 / a0], [1.0, a1 / a0, a2 / a0]


def get_filter_response(filters, frequencies, fs=48000):
    """Calculates the combined frequency response in dB of a cascade of filters.

    Args:
        filters (list): List of filter parameters tuples (ftype, fc, gain, q).
        frequencies (np.ndarray): Frequencies to evaluate the response at.
        fs (float): Sampling frequency in Hz. Defaults to 48000.

    Returns:
        np.ndarray: Response in dB.
    """
    w_eval = 2 * np.pi * frequencies / fs
    total_h = np.ones(len(frequencies), dtype=complex)
    for filt in filters:
        b, a = get_biquad_coefs(filt[0], filt[1], fs, filt[2], filt[3])
        _, h = freqz(b, a, worN=w_eval)
        total_h *= h
    return 20 * np.log10(np.abs(total_h))
