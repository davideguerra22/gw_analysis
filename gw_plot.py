#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Copyright (C) 2026 Davide Guerra
"""
Makes one interactive HTML page from a file written by gw_analysis.py.
In the page you can choose the extraction radii, the mode, psi4 or h and the
part (real, imaginary, amplitude), plotted vs the retarded time.

The page needs no python: open it in a browser (Plotly is loaded from the web).
The arrays are stored in single precision to keep the file small.
"""

import argparse
import base64
import json
import math
import os

import h5py
import numpy as np



# colours of the radii: 'plasma' colormap (cut before the yellow end),
# deep blue for the largest radius and orange for the smallest one
PALETTE = ['#0d0887', '#41049d', '#6a00a8', '#8f0da4', '#b12a90',
           '#cc4778', '#e16462', '#f2844b', '#fca636']


def colors(n):
    """n colours along PALETTE, the first one for the largest radius"""
    rgb = np.array([[int(c[i:i+2], 16) for i in (1, 3, 5)] for c in PALETTE], dtype=float)
    x = np.linspace(0, len(PALETTE) - 1, len(PALETTE))
    out = []
    for v in np.linspace(0, len(PALETTE) - 1, n) if n > 1 else [0]:
        out.append('#%02x%02x%02x' % tuple(int(round(np.interp(v, x, rgb[:, k]))) for k in range(3)))
    return out


def b64(x):
    """float32 array -> base64 string (decoded in the browser)"""
    return base64.b64encode(np.ascontiguousarray(x, dtype='<f4').tobytes()).decode()


def info_line(f):
    a = f['simulation'].attrs
    s = f['sampling'].attrs
    out = [str(a['system'])]
    for k, fmt in [('name', '%s'), ('eos', 'EOS %s')]:
        if k in a and str(a[k]):
            out.append(fmt % a[k])
    out.append('Madm = %.6g' % a['Madm'])
    if not math.isnan(a['omega0']):
        out.append('Omega0 = %.6g rad/s' % a['omega0'])
    out.append('N = %d, dt = %.4g ms' % (s['N'], s['dt_ms']))
    return ' &middot; '.join(out)


def build_data(fname, radii=None, lmax=None, step=1):
    f = h5py.File(fname, 'r')
    groups = list(f['radii'])
    if radii:
        groups = [g for g in groups if any(abs(f['radii'][g].attrs['R'] - R) < 0.005*R for R in radii)]
        if not groups:
            raise SystemExit('none of the radii %s is in the file' % radii)
    merger = bool(f['simulation'].attrs.get('has_merger', 0))      # 0 for a single NS

    data = {'info': info_line(f), 'merger': merger, 'radii': [], 'modes': [], 'arr': {}}
    for g in groups:
        G = f['radii'][g]
        riso = G.attrs['Riso']
        data['radii'].append({'name': g, 'R': float(G.attrs['R']), 'km': round(float(G.attrs['Riso_km']), 1),
                              'tmerg': float(G.attrs['t_merg_ms']) if merger else None,
                              't': b64(G['tret_ms'][::step])})
        modes = [lm for lm in G if lm.startswith('l') and (lmax is None or int(lm[1:lm.index('m')]) <= lmax)]
        if not data['modes']:
            data['modes'] = modes
        for lm in modes:
            M = G[lm]
            data['arr']['%s/%s/psi4/0' % (g, lm)] = b64(M['psi4_re'][::step]*riso)     # plot r*psi4
            data['arr']['%s/%s/psi4/1' % (g, lm)] = b64(M['psi4_im'][::step]*riso)
            data['arr']['%s/%s/rh/0' % (g, lm)] = b64(M['rh_plus'][::step])
            data['arr']['%s/%s/rh/1' % (g, lm)] = b64(M['rh_cross'][::step])
    f.close()
    for r, c in zip(data['radii'][::-1], colors(len(data['radii']))):
        r['color'] = c
    return data


# check box shown only when there is a merger (binaries)
SHIFT_HTML = """<div class="grp"><span class="lab"></span>
  <label><input type="checkbox" id="shift"> time from the merger</label></div>
"""

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>GW viewer</title>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
<style>
  body { font-family: system-ui, sans-serif; margin: 16px; color: #222; }
  #info { color: #555; margin-bottom: 10px; }
  .grp { margin: 6px 0; }
  .grp > span.lab { font-weight: 600; display: inline-block; width: 110px; }
  select { font-size: 14px; padding: 4px; }
  .btn { font-size: 14px; padding: 5px 13px; margin-right: 4px; cursor: pointer;
         border: 1px solid #888; background: #f4f4f4; border-radius: 4px; }
  .btn.active { background: #1f77b4; color: #fff; border-color: #1f77b4; }
  .rad { margin-right: 12px; white-space: nowrap; }
  #plot { width: 100%; height: 600px; }
</style>
</head>
<body>
<h2>__TITLE__</h2>
<div id="info">__INFO__</div>

<div class="grp"><span class="lab">Radius:</span><span id="rgrp"></span></div>
<div class="grp"><span class="lab">Mode:</span><select id="mode"></select></div>
<div class="grp" id="qgrp"><span class="lab">Quantity:</span></div>
<div class="grp" id="pgrp"><span class="lab">Part:</span></div>
__SHIFT__<div id="plot"></div>

<script>
const DATA = __DATA__;
let quant = 'rh', part = 're';

// base64 -> float32 numbers, decoded only when needed
const cache = {};
function decode(key, b64) {
  if (!(key in cache)) {
    const s = atob(b64);
    const b = new Uint8Array(s.length);
    for (let i = 0; i < s.length; i++) b[i] = s.charCodeAt(i);
    cache[key] = Array.from(new Float32Array(b.buffer));
  }
  return cache[key];
}
const arr = key => decode(key, DATA.arr[key]);
const tret = r => decode('t:' + r.name, r.t);

// radius check boxes (the largest one selected)
const rgrp = document.getElementById('rgrp');
DATA.radii.forEach((r, i) => {
  const l = document.createElement('label');
  l.className = 'rad';
  l.innerHTML = '<input type="checkbox" id="r' + i + '"' +
                (i === DATA.radii.length - 1 ? ' checked' : '') + '> ' + r.R + ' (' + r.km + ' km)';
  rgrp.appendChild(l);
  document.getElementById('r' + i).addEventListener('change', draw);
});

const msel = document.getElementById('mode');
DATA.modes.forEach(m => {
  const o = document.createElement('option');
  o.value = m; o.textContent = m;
  if (m === 'l2m2') o.selected = true;
  msel.appendChild(o);
});
msel.addEventListener('change', draw);
const shiftBox = document.getElementById('shift');      // not there for a single NS
if (shiftBox) shiftBox.addEventListener('change', draw);

function buttons(id, items, get, set) {
  const g = document.getElementById(id);
  items.forEach(([v, label]) => {
    const b = document.createElement('button');
    b.className = 'btn' + (v === get() ? ' active' : '');
    b.textContent = label;
    b.onclick = () => {
      set(v);
      g.querySelectorAll('.btn').forEach(x => x.classList.toggle('active', x === b));
      draw();
    };
    g.appendChild(b);
  });
}
buttons('qgrp', [['psi4', '\\u03C8\\u2084'], ['rh', 'h']], () => quant, v => { quant = v; });
buttons('pgrp', [['re', 'Re / plus'], ['im', 'Im / cross'], ['abs', 'amplitude']],
        () => part, v => { part = v; });

function draw() {
  const lm = msel.value, q = quant;
  const shift = shiftBox !== null && shiftBox.checked;
  const traces = [];
  DATA.radii.forEach((r, i) => {
    if (!document.getElementById('r' + i).checked) return;
    const re = arr(r.name + '/' + lm + '/' + q + '/0');
    const im = arr(r.name + '/' + lm + '/' + q + '/1');
    let y = re;
    if (part === 'im') y = im;
    if (part === 'abs') y = re.map((v, j) => Math.hypot(v, im[j]));
    let t = tret(r);
    if (shift) t = t.map(v => v - r.tmerg);
    traces.push({x: t, y: y, mode: 'lines', name: 'R = ' + r.R,
                 line: {color: r.color, width: 1.2}});
  });

  let ylab;
  if (quant === 'psi4') ylab = {re: 'Re(r \\u03C8\\u2084)', im: 'Im(r \\u03C8\\u2084)', abs: '|r \\u03C8\\u2084|'}[part];
  else ylab = {re: 'r h\\u208A', im: 'r h\\u00D7', abs: 'r |h|'}[part];
  const xlab = shift ? 't_ret \\u2212 t_merg [ms]' : 't_ret [ms]';

  Plotly.react('plot', traces, {
    margin: {l: 75, r: 15, t: 10, b: 50},
    xaxis: {title: xlab},
    yaxis: {title: ylab + ' [code units]', exponentformat: 'power'},
    legend: {x: 0.01, y: 0.99},
    showlegend: true,
  }, {responsive: true, displaylogo: false});
}

draw();
</script>
</body>
</html>
"""


def main():
    ap = argparse.ArgumentParser(
        prog='gw_plot.py', description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='examples:\n'
               '  python3 gw_plot.py data/H5/gw_analysis.h5\n'
               '  python3 gw_plot.py data/H5/gw_analysis.h5 --radii 759.46 1139.18 --lmax 3\n'
               '  python3 gw_plot.py data/H5/gw_analysis.h5 --step 2 -o gw.html\n')
    ap.add_argument('h5file', metavar='FILE.h5', help='file written by gw_analysis.py')
    ap.add_argument('-o', '--out', metavar='FILE.html', help='output page (default: FILE.html)')
    ap.add_argument('--radii', type=float, nargs='+', metavar='R', help='only these radii (default: all)')
    ap.add_argument('--lmax', type=int, metavar='L', help='only the modes with l <= L (default: all)')
    ap.add_argument('--step', type=int, default=1, metavar='N',
                    help='keep one point every N (default 1, all the points)')
    args = ap.parse_args()

    if not os.path.isfile(args.h5file):
        raise SystemExit('ERROR: %s not found' % args.h5file)
    out = args.out or os.path.splitext(args.h5file)[0] + '.html'

    data = build_data(args.h5file, args.radii, args.lmax, max(args.step, 1))
    with h5py.File(args.h5file, 'r') as f:
        name = f['simulation'].attrs.get('name', '')
    title = 'GW viewer' + (' &mdash; %s' % name if str(name) else '')
    html = (HTML_TEMPLATE.replace('__TITLE__', title).replace('__INFO__', data.pop('info'))
            .replace('__SHIFT__', SHIFT_HTML if data['merger'] else '')
            .replace('__DATA__', json.dumps(data)))
    with open(out, 'w') as fh:
        fh.write(html)
    print('Wrote %s (%.0f MB): %d radii, %d modes'
          % (out, os.path.getsize(out)/1e6, len(data['radii']), len(data['modes'])))
    print('Open it in a browser (internet needed to load Plotly).')
    if os.path.getsize(out) > 50e6:
        print('The file is big: use --radii, --lmax or --step to make it smaller.')


if __name__ == '__main__':
    main()
