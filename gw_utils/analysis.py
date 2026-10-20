# Copyright (C) 2026 Davide Guerra
#
# psi4 -> h and merger time.
# Same routines (and names) as pycactus3/UtilityAnalysis.py, rewritten to work
# on plain arrays (t, psi4) instead of the {'time','re','im'} dictionaries.
# The results are identical to the pycactus ones.
#
# psi4 = d^2/dt^2 (h_plus - i h_cross). As in pycactus, NIntegratePsi4_filter
# returns the conjugate of the integral, i.e. h_plus + i h_cross.

import numpy as np
import scipy.integrate
import scipy.signal


def Riso(r=0, M=0):
    """areal radius of the coordinate radius r"""
    if r == 0:
        return r
    if M > 1e-8:
        return r*(1+M/(2*r))**2
    return r


def RetardedTime(t, r=0, M=0):
    if r == 0:
        return t
    if M > 1e-8:
        rA = r*(1+M/(2*r))**2
        rstar = rA + 2*M*np.log(rA/(2*M)-1)
    else:
        rstar = r
    return t - rstar


def NIntegratePsi4(t, psi4, Nint=2, r=0, M=0, order=2):
    """Nint time integrals of psi4 (zero before t_ret = 0), minus a polynomial fit"""
    t_ret = RetardedTime(t, r, M)
    idx_t0 = np.searchsorted(t_ret, 0)
    integrand = np.array(psi4, dtype=complex)
    for i in range(Nint):
        integrand[0:idx_t0] = 0
        integrand[idx_t0:] = scipy.integrate.cumulative_trapezoid(integrand[idx_t0:], x=t_ret[idx_t0:],
                                                                  initial=0)
    h = integrand
    h_int_const = np.polyfit(t_ret[idx_t0:], h[idx_t0:], order)
    h[idx_t0:] = h[idx_t0:] - np.polyval(h_int_const, t_ret[idx_t0:])
    return h


def NIntegratePsi4_filter(t, psi4, f0, Nint=2, r=0, M=0):
    """integration + butterworth high-pass filter at f0 (code units)"""
    order = Nint-1
    fnyq = 0.5/(np.diff(t)[0])
    h = np.conj(NIntegratePsi4(t, psi4, Nint, r, M, order))
    b, a = scipy.signal.iirdesign(f0/fnyq, f0/fnyq/10.0, 1e-2, 80, ftype="butter")
    return scipy.signal.filtfilt(b, a, h, padtype='constant')


def FindMaximumTimeSeries(x, f):
    fval = np.abs(f)
    idx = int(np.argmax(fval))
    return (x[idx], fval[idx], idx)


def GWfrequency(t, h):
    """instantaneous frequency of a complex mode, |d phase/dt| / 2pi"""
    phase = np.unwrap(np.angle(h))
    return np.abs(np.gradient(phase, t))/(2*np.pi)
