#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2026 Davide Guerra
"""
Reads the psi4 multipoles of an Einstein Toolkit simulation (Multipole ASCII
files mp_psi4_l*_m*_r*.asc) and writes one HDF5 file with psi4 and the strain
at every extraction radius, the time sampling and the information on the
simulated system. h is computed with the pycactus3 routines (rewritten in
gw_utils/analysis.py).

SIM_DIR is the folder with the output-NNNN folders, one for every restart of
the simulation from checkpoint. The script asks in the terminal: system type,
ADM mass, ADM angular momentum, Omega0, optional information on the system
(name, masses, radii, EOS, ...) and the name of the output file. The answers
are saved in <output>_info.json.
"""

import argparse
import getpass
import glob
import json
import os
import sys
import warnings
from datetime import datetime

import numpy as np

from gw_utils import __version__
from gw_utils import analysis as AA
from gw_utils import multipole as MP
from gw_utils import output as OUT
from gw_utils import siminfo as SI
from gw_utils import units as U

OUTFILE = os.path.join('H5', 'gw_analysis.h5')    # default, relative to SIM_DIR
FCUT_NS = 500.0                                   # Hz, default cut-off for a single NS


def parse_args():
    p = argparse.ArgumentParser(
        prog='gw_analysis.py', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='examples:\n'
               '  python3 gw_analysis.py data                       answer the questions\n'
               '  python3 gw_analysis.py data --info data/H5/gw_analysis_info.json\n'
               '                                                    re-use the answers of a previous run\n'
               '  python3 gw_analysis.py data --radii 759.46 1139.18 --lmax 3\n'
               '  python3 gw_analysis.py --edit-info data/H5/gw_analysis.h5\n'
               '                                                    add/change the system info\n'
               '  python3 gw_plot.py data/H5/gw_analysis.h5         interactive html plot (optional)\n')
    p.add_argument('simdir', nargs='?', default='.', metavar='SIM_DIR',
                   help='simulation folder with the output-NNNN folders (default: current folder)')
    p.add_argument('-o', '--output', metavar='FILE.h5', help='output file (default: asked, SIM_DIR/%s)' % OUTFILE)
    p.add_argument('--info', metavar='FILE.json', help='answers of a previous run, to skip the questions')
    p.add_argument('--edit-info', metavar='FILE.h5', help='only add/change the system info of FILE.h5')
    p.add_argument('--radii', type=float, nargs='+', metavar='R', help='extraction radii to use (default: all)')
    p.add_argument('--lmax', type=int, metavar='L', help='use only the modes with l <= L (default: all)')
    p.add_argument('--fcut', type=float, metavar='HZ',
                   help='cut-off frequency of the integration in Hz (default: Omega0/pi, asked for a single NS)')
    return p.parse_args()


def warn(message, category, filename, lineno, file=None, line=None):
    print('  WARNING: %s' % message, file=sys.stderr)


def pick_radii(rext, wanted):
    if not wanted:
        return rext
    out = []
    for R in wanted:
        r = min(rext, key=lambda x: abs(float(x) - R))
        if abs(float(r) - R) > 0.005*R:
            raise SystemExit('ERROR: radius %g not found (available: %s)' % (R, ', '.join(rext)))
        out.append(r)
    return sorted(set(out), key=float)


def khz(f):
    return '%.4g kHz' % (f/1e3) if f >= 1e3 else '%.4g Hz' % f


def relpath(p):
    r = os.path.relpath(p)
    return p if r.startswith('..') else r


def txt(x):
    return x.decode() if isinstance(x, bytes) else str(x)


def previous_answers(simdir, interactive):
    """json file of a previous run of this simulation, if the user wants to use it"""
    found = sorted(set(glob.glob(os.path.join(simdir, 'H5', '*_info.json')) +
                       glob.glob(os.path.join(simdir, '*_info.json'))))
    if not found:
        return None
    if not interactive:
        if len(found) == 1:
            print('Answers    : %s (previous run)' % relpath(found[0]))
            return found[0]
        return None
    print('\n--- Answers of a previous run')
    for i, jf in enumerate(found, 1):
        try:
            with open(jf) as f:
                j = json.load(f)
            what = ', '.join(str(x) for x in (j.get('system'), 'Madm = %s' % j.get('Madm'), j.get('name'),
                                              j.get('output') and relpath(j['output'])) if x)
        except Exception:
            what = 'cannot be read'
        print('     %d) %s  (%s)' % (i, relpath(jf), what))
    if len(found) == 1:
        return found[0] if SI.ask_yn('Use the same answers?', default=True) else None
    while True:
        s = SI.ask('Which one (Enter = none)', str)
        if not s:
            return None
        if s.isdigit() and 1 <= int(s) <= len(found):
            return found[int(s) - 1]


def summary(sim, samp, proc, rattrs):
    """summary printed at the end of the run"""
    L = []
    name = '' if SI.isblank(sim.get('name', '')) else ', ' + txt(sim['name'])
    L.append('System      : %s - %s%s' % (txt(sim['system']), txt(sim['system_long']), name))
    L.append('Madm        : %.15g M_sun' % sim['Madm'])
    L.append('Jadm        : %s' % ('(blank)' if np.isnan(sim['Jadm']) else '%.15g M_sun^2' % sim['Jadm']))
    if np.isnan(sim['omega0']):
        L.append('Omega0      : (blank)')
    else:
        L.append('Omega0      : %.15g rad/s%s' % (sim['omega0'],
                 ' (f_gw0 = %s)' % khz(sim['f_gw0']) if 'f_gw0' in sim else ''))
    opt = SI.optional(txt(sim['system']))
    n = sum(not SI.isblank(sim.get(o[0], '')) for o in opt)
    L.append('Other info  : %d of %d entries' % (n, len(opt)))
    outs = [txt(o) for o in samp['outputs']]
    L.append('Outputs     : %d (%s ... %s), %d repeated times removed' % (len(outs), outs[0], outs[-1], samp['ndup']))
    L.append('Radii       : %s' % ', '.join('%g' % r for r in proc['radii']))
    modes = [txt(m) for m in proc['modes']]
    L.append('Modes       : %d (%s ... %s)' % (len(modes), modes[0], modes[-1]))
    L.append('Samples     : %d, t = %g ... %g (%.4f ms), dt = %g = %.4e ms'
             % (samp['N'], samp['t0'], samp['tf'], samp['tf_ms'], samp['dt'], samp['dt_ms']))
    if not samp['uniform']:
        L.append('              WARNING: time step not uniform (%g ... %g)' % (samp['dt_min'], samp['dt_max']))
    L.append('Frequencies : fs = %s, Nyquist = %s, df = %s'
             % (khz(samp['fs_Hz']), khz(samp['fnyq_Hz']), khz(samp['df_Hz'])))
    L.append('Cut-off f0  : %s (%s)' % (khz(proc['f0_Hz']), txt(proc['f0_from'])))
    if sim['has_merger']:
        L.append('Merger      : R, t_merg (retarded time), f_gw, time after the merger (df)')
        for g, a in rattrs.items():
            L.append('   %-9s %8.4f ms   %-10s %7.3f ms (%s)' % (g[1:], a['t_merg_ms'], khz(a['f_merg_Hz']),
                                                               a['T_post_ms'], khz(a['df_post_Hz'])))
    return L


def extract(time, psi4, r, madmi, f00):
    """psi4 -> r*h for one radius"""
    r_iso = AA.Riso(r=r, M=madmi)
    tret = AA.RetardedTime(time, r=r_iso, M=madmi)
    out = {}
    for lm, p in psi4.items():
        out[lm] = {'psi4': p, 'rh': r_iso*AA.NIntegratePsi4_filter(time, p, f00, 2, r_iso, madmi)}
    return r_iso, tret, out


def dsets(d):
    """complex arrays -> real datasets of one mode, rh = r (h_plus + i h_cross)"""
    return {'psi4_re': d['psi4'].real, 'psi4_im': d['psi4'].imag,
            'rh_plus': d['rh'].real, 'rh_cross': d['rh'].imag}


def sampling(time, tinfo):
    N = len(time)
    dt = time[1] - time[0]
    T = time[-1] - time[0]
    s = {'N': N, 'dt': dt, 'dt_ms': dt*U.CU_to_ms, 'dt_s': dt*U.CU_to_s,
         't0': time[0], 'tf': time[-1], 't0_ms': time[0]*U.CU_to_ms, 'tf_ms': time[-1]*U.CU_to_ms,
         'T': T, 'T_ms': T*U.CU_to_ms, 'T_s': T*U.CU_to_s,
         'fs': 1/dt, 'fnyq': 0.5/dt, 'df': 1/(N*dt),
         'fs_Hz': 1/(dt*U.CU_to_s), 'fnyq_Hz': 0.5/(dt*U.CU_to_s), 'df_Hz': 1/(N*dt*U.CU_to_s)}
    s.update(tinfo)
    return s


def edit_info(fname):
    if not os.path.isfile(fname):
        raise SystemExit('ERROR: %s not found' % fname)
    info = OUT.read_sim(fname)
    print('\n%s: %s, Madm = %.15g' % (os.path.basename(fname), info['system'], info['Madm']))
    SI.ask_optional(info, edit=True)
    OUT.update_sim(fname, SI.sim_attrs(info))
    jfile = os.path.splitext(fname)[0] + '_info.json'
    saved = SI.load_json(jfile) if os.path.isfile(jfile) else {}
    saved.update({k: info[k] for k in ('system', 'Madm', 'Jadm', 'omega0')})
    saved.update({o[0]: info[o[0]] for o in SI.optional(info['system'])})
    SI.save_json(jfile, saved)
    print('\nUpdated %s and %s' % (fname, jfile))


def main():
    args = parse_args()
    warnings.showwarning = warn
    if args.edit_info:
        return edit_info(args.edit_info)

    startTime = datetime.now()
    interactive = sys.stdin.isatty()
    simdir = os.path.abspath(args.simdir)

    print('\ngw_analysis.py %s' % __version__)
    print('Simulation : %s' % simdir)
    outs, rext, modes = MP.ListPsi4(simdir)
    rext = pick_radii(rext, args.radii)
    modes = [(l, m) for (l, m) in modes if args.lmax is None or l <= args.lmax]
    print('Outputs    : %d (%s ... %s)' % (len(outs), outs[0][0], outs[-1][0]))
    print('Radii      : %s' % ', '.join(rext))
    print('Modes      : %d (l = %d...%d)' % (len(modes), modes[0][0], modes[-1][0]))

    # ---- information on the system
    jinfo = args.info or previous_answers(simdir, interactive)
    info = SI.collect(interactive, jinfo)
    binary = info['system'] in SI.BINARIES
    madmi = float(info['Madm'])

    if args.fcut:
        info['fcut'] = args.fcut
    if SI.isblank(info.get('fcut')) and not binary:
        if interactive:
            info['fcut'] = SI.ask('Cut-off frequency of the integration [Hz]', float, FCUT_NS)
        else:
            info['fcut'] = FCUT_NS
            warnings.warn('cut-off frequency set to %g Hz (use --fcut)' % FCUT_NS)
    if SI.isblank(info.get('fcut')):
        f00 = float(info['omega0'])/np.pi * U.CU_to_s
        f0_from = 'omega0/pi'
    else:
        f00 = float(info['fcut']) * U.CU_to_s
        f0_from = 'user'

    if args.output:
        info['output'] = args.output
    elif SI.isblank(info.get('output')):
        default = os.path.join(simdir, OUTFILE)
        info['output'] = SI.ask('Output file', str, relpath(default)) if interactive else default
    fname = os.path.abspath(info['output'])
    if not fname.endswith(('.h5', '.hdf5')):
        fname += '.h5'
    info['output'] = fname
    os.makedirs(os.path.dirname(fname), exist_ok=True)
    jfile = os.path.splitext(fname)[0] + '_info.json'
    SI.save_json(jfile, info)

    # ---- psi4
    print('\nReading psi4')
    time, psi4, tinfo = MP.ReadPsi4(outs, rext, modes)
    rext = [r for r in rext if r in psi4]
    dt = time[1] - time[0]
    if not 0 < f00 < 0.5/dt:
        raise SystemExit('ERROR: cut-off frequency %g Hz above Nyquist' % (f00/U.CU_to_s))
    print('  %d times, t = %g ... %g, dt = %g' % (len(time), time[0], time[-1], dt))

    # ---- h
    print('\nComputing h (f0 = %s)' % khz(f00/U.CU_to_s))
    radii = {}
    for r in rext:
        r_iso, tret, h = extract(time, psi4[r], float(r), madmi, f00)
        attrs = {'R': float(r), 'Riso': r_iso, 'Riso_km': r_iso*U.CU_to_km, 'rstar': time[0] - tret[0]}
        if binary:
            # merger = max of |rh_22|, then what is left after it (for the FFT of the post-merger)
            if 'l2m2' not in h:
                raise SystemExit('ERROR: no l2m2 mode at R = %s, needed for the merger time' % r)
            t_merg, A, i = AA.FindMaximumTimeSeries(tret, h['l2m2']['rh'])
            npost = int(np.sum(tret >= t_merg))
            attrs.update({'t_merg': t_merg, 't_merg_ms': t_merg*U.CU_to_ms,
                          'f_merg_Hz': AA.GWfrequency(tret, h['l2m2']['rh'])[i]/U.CU_to_s, 'A_merg': A,
                          'N_post': npost, 'T_post_ms': (tret[-1] - t_merg)*U.CU_to_ms,
                          'df_post_Hz': 1/(max(npost, 1)*dt*U.CU_to_s)})
            print('  R = %8s   t_merg = %.4f ms' % (r, t_merg*U.CU_to_ms))
        else:
            print('  R = %8s' % r)
        radii['R' + r] = {'attrs': attrs, 'tret': tret, 'tret_ms': tret*U.CU_to_ms,
                          'modes': {lm: dsets(d) for lm, d in h.items()}}

    # ---- output
    sim = SI.sim_attrs(info)
    samp = sampling(time, tinfo)
    proc = {'f0': f00, 'f0_Hz': f00/U.CU_to_s, 'f0_from': f0_from,
            'integration': 'NIntegratePsi4_filter (pycactus3)',
            'radii': np.array([float(r) for r in rext]), 'modes': list(h)}
    title = 'GW data, %s' % SI.SYSTEMS[info['system']]
    if not SI.isblank(info.get('name')):
        title += ', ' + info['name']
    root = {'title': title, 'date': datetime.now().strftime('%Y-%m-%d %H:%M'),
            'code': 'gw_analysis.py %s' % __version__, 'user': getpass.getuser(), 'simdir': simdir}
    lines = summary(sim, samp, proc, {k: v['attrs'] for k, v in radii.items()})
    OUT.WriteGW(fname, root, sim, samp, time, proc, U.as_dict(), radii)

    # ---- summary
    print('\n' + '-'*72)
    print('Output      : %s (%.0f MB)' % (relpath(fname), os.path.getsize(fname)/1024**2))
    print('Answers     : %s' % relpath(jfile))
    print('\n'.join(lines))
    if not SI.isblank(info.get('system')) and sum(not SI.isblank(info[o[0]]) for o in SI.optional(info['system'])) == 0:
        print('(the information on the system can be added with --edit-info %s)' % relpath(fname))
    print('Done in %s' % (datetime.now() - startTime))


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        sys.exit('\nAborted.')
    except (FileNotFoundError, ValueError) as e:
        sys.exit('ERROR: %s' % e)
