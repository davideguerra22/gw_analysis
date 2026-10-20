# Copyright (C) 2026 Davide Guerra
#
# Reading of the Multipole ASCII files mp_psi4_l*_m*_r*.asc.
# The files are looked for in every output-NNNN folder of the simulation (at any
# depth), or in the folder itself if there are no output-NNNN folders.
# The outputs are merged as in the old h22.py: concatenated in order and the
# repeated times (restarts) removed with np.unique.

import os
import re
import warnings

import numpy as np

RE_FILE = re.compile(r'^mp_psi4_l(\d+)_m(-?\d+)_r(\d+(?:\.\d+)?)\.asc$', re.IGNORECASE)
RE_OUTPUT = re.compile(r'^output-(\d+)$')


def ModeName(l, m):
    return 'l%dm%d' % (l, m)


def ListPsi4(simdir):
    """Returns the outputs [(name, {(r, l, m): file})], the radii and the modes found."""
    simdir = os.path.abspath(simdir)
    if not os.path.isdir(simdir):
        raise FileNotFoundError('directory not found: %s' % simdir)
    names = sorted((n for n in os.listdir(simdir)
                    if RE_OUTPUT.match(n) and os.path.isdir(os.path.join(simdir, n))),
                   key=lambda n: int(RE_OUTPUT.match(n).group(1)))
    if not names:
        names = ['.']

    outs = []
    for name in names:
        files = {}
        for root, dirs, fnames in os.walk(os.path.join(simdir, name)):
            dirs.sort()
            for fn in sorted(fnames):
                x = RE_FILE.match(fn)
                if x:
                    files.setdefault((x.group(3), int(x.group(1)), int(x.group(2))), os.path.join(root, fn))
        if files:
            outs.append((os.path.basename(simdir) if name == '.' else name, files))
    if not outs:
        raise FileNotFoundError('no mp_psi4_l*_m*_r*.asc files in %s' % simdir)

    keys = set().union(*[f for _, f in outs])
    radii = sorted({k[0] for k in keys}, key=float)
    modes = sorted({(k[1], k[2]) for k in keys})
    return outs, radii, modes


def dataimport(files):
    """concatenates the files and removes the repeated times (as in h22.py)"""
    data_list = []
    for f in files:
        try:
            data = np.loadtxt(f)
        except Exception:
            continue
        if data.size > 0:
            if len(data.shape) == 1:
                data = data.reshape(1, -1)
            data_list.append(data)
    if not data_list:
        return None, 0
    data_all = np.concatenate(data_list)
    _, idx = np.unique(data_all[:, 0], return_index=True)
    return data_all[idx], len(data_all) - len(idx)


def ReadPsi4(outs, radii, modes, verbose=True):
    """Returns time, psi4[r][lm] (complex) and some info on the time sampling.

    All the modes must have the same times: the ones that don't (missing files)
    are skipped with a warning.
    """
    t = None
    psi4 = {r: {} for r in radii}
    ndup = 0
    for r in radii:
        if verbose:
            print('    R = %s' % r, flush=True)
        for (l, m) in modes:
            files = [f[(r, l, m)] for _, f in outs if (r, l, m) in f]
            dat, nd = dataimport(files)
            if dat is None:
                continue
            ndup = max(ndup, nd)
            if t is None:
                t = dat[:, 0]
            if len(dat) != len(t) or np.max(np.abs(dat[:, 0] - t)) > 1e-6:
                warnings.warn('R = %s, l=%d m=%d: times different from the other modes, skipped' % (r, l, m))
                continue
            psi4[r][ModeName(l, m)] = dat[:, 1] + 1j*dat[:, 2]

    # time range of every output folder (from the first file found)
    k0 = next(iter(outs[0][1]))
    t0, tf = [], []
    for _, f in outs:
        k = k0 if k0 in f else next(iter(f))
        d = np.loadtxt(f[k], ndmin=2)
        t0.append(d[0, 0] if d.size else np.nan)
        tf.append(d[-1, 0] if d.size else np.nan)

    dts = np.diff(t)
    dt = np.median(dts)
    uniform = bool(np.max(np.abs(dts - dt)) <= 1e-4*dt)
    if not uniform:
        warnings.warn('the time step is not uniform (dt from %g to %g): is an output folder missing?'
                      % (dts.min(), dts.max()))

    info = {'outputs': [n for n, _ in outs], 'outputs_t0': np.array(t0), 'outputs_tf': np.array(tf),
            'ndup': ndup, 'dt_min': dts.min(), 'dt_max': dts.max(), 'uniform': int(uniform)}
    return t, {r: p for r, p in psi4.items() if p}, info
