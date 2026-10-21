# Copyright (C) 2026 Davide Guerra
#
# Writing of the output HDF5 file (layout in the README).

import os

import h5py
import numpy as np

UNITS = {
    'time': 'code units', 'time_ms': 'ms', 'tret': 'code units', 'tret_ms': 'ms',
    'psi4_re': 'code units', 'psi4_im': 'code units',
    'rh_plus': 'code units', 'rh_cross': 'code units',
}


def set_attrs(obj, attrs):
    for k, v in attrs.items():
        if isinstance(v, (list, tuple)):
            v = np.array(v, dtype=h5py.string_dtype())
        obj.attrs[k] = v


def write_dset(g, name, data):
    ds = g.create_dataset(name, data=np.asarray(data, dtype=float))
    if name in UNITS:
        ds.attrs['units'] = UNITS[name]


def write_radius(g, wave):
    set_attrs(g, wave['attrs'])
    write_dset(g, 'tret', wave['tret'])
    write_dset(g, 'tret_ms', wave['tret_ms'])
    for lm, dsets in wave['modes'].items():
        gm = g.create_group(lm)
        for name, data in dsets.items():
            write_dset(gm, name, data)


def WriteGW(fname, root, sim, sampling, time, processing, units, radii):
    """writes everything in fname (first in fname.tmp, renamed at the end)"""
    tmp = fname + '.tmp'
    cfg = h5py.get_config()
    old, cfg.track_order = cfg.track_order, True      # keep the groups in the order they are written
    try:
        with h5py.File(tmp, 'w') as f:
            set_attrs(f, root)
            set_attrs(f.create_group('simulation'), sim)
            g = f.create_group('sampling')
            set_attrs(g, sampling)
            write_dset(g, 'time', time)
            write_dset(g, 'time_ms', time*units['CU_to_ms'])
            set_attrs(f.create_group('processing'), processing)
            set_attrs(f.create_group('units'), units)
            g = f.create_group('radii')
            for name, wave in radii.items():
                write_radius(g.create_group(name), wave)
    finally:
        cfg.track_order = old
    os.replace(tmp, fname)


def read_sim(fname):
    with h5py.File(fname, 'r') as f:
        return dict(f['simulation'].attrs)


def update_sim(fname, sim):
    with h5py.File(fname, 'r+') as f:
        set_attrs(f['simulation'], sim)
