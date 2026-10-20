# gw_analysis

`gw_analysis.py` reads the psi4 multipoles of an Einstein Toolkit simulation (thorn `Multipole`) and writes a single HDF5 file with:

- psi4 and the strain r·h for every mode (all the l and m written by Multipole) at every extraction radius;
- the time sampling (number of samples, time step, sampling rate, Nyquist frequency, frequency resolution) in code and physical units, for Fourier analysis;
- the information on the simulated system (BNS, BBH, BHNS or single NS, ADM mass and angular momentum, initial angular velocity, masses, radii, EOS, ...).

The strain is computed with the same routines as the pycactus3 package (rewritten in `gw_utils/`), so the results are identical to the ones obtained with pycactus3. Only `numpy`, `scipy` and `h5py` are needed.

`gw_plot.py` (optional) makes an interactive HTML page from the output file, to look at the data in a browser.

```
gw_analysis/
├── gw_analysis.py      main script
├── gw_plot.py          interactive HTML plot (optional)
├── gw_utils/           reading, analysis routines, questions, output
├── requirements.txt
└── README.md
```

## Installation

```bash
git clone <repository>
pip install -r requirements.txt
```

## Input data

The script needs the ASCII output of `Multipole`, the files `mp_psi4_l<l>_m<m>_r<R>.asc`. The simulation is expected to be split in `output-NNNN` folders, one for every run: each time the simulation is started again from the last checkpoint (e.g. every day of run) its output goes in a new folder. Give the script the folder that contains them:

```
SIM_DIR/
├── output-0000/.../mp_psi4_l2_m2_r1139.18.asc
├── output-0001/.../mp_psi4_l2_m2_r1139.18.asc
└── ...
```

The files can be at any depth inside each `output-NNNN` (e.g. `output-0000/Multipole/` or `output-0000/data/Multipole/`). If there are no `output-NNNN` folders, the files are searched in `SIM_DIR` itself. The folders are joined in order and the times repeated after a restart from checkpoint are removed. All the modes are kept, also l = 0, 1 (they are zero, since psi4 has spin weight −2).

## Usage

```bash
python3 gw_analysis.py SIM_DIR
```

The script can be run from any folder, e.g. `python3 ~/gw_analysis/gw_analysis.py data`. `python3 gw_analysis.py --help` shows all the options.

The script asks:

- the system type (BNS, BBH, BHNS, NS);
- the initial ADM mass;
- the initial ADM angular momentum and orbital angular velocity Ω₀. These are required for binaries and can be skipped for a single NS. Ω₀ can be given in rad/s (as in LORENE) or in code units (`0.0087 cu`).

It can also store, if you want:

- **information on the system:** name, description, initial data and evolution codes, finest grid spacing, initial separation, masses (gravitational and baryonic), radii, tidal deformabilities, spins, central density, EOS name and type, EOS of the initial data, EOS during the evolution, EOS table, Γ_th, notes. Any entry can be skipped with Enter and stays blank in the file (NaN or empty string). Total mass, mass ratio, chirp mass and compactness are computed from the masses and radii, when given;
- **the output file name:** the default is `SIM_DIR/H5/gw_analysis.h5`.

For a single NS the cut-off frequency of the integration is also asked (default 500 Hz).

The answers are saved in `<output>_info.json`. When the script is run again on the same simulation (e.g. when the simulation goes on), it finds this file in `SIM_DIR/H5/` or `SIM_DIR/`, shows what is in it and asks whether to use the same answers. With Enter nothing else is asked. If there is more than one file, it asks which one to use. In a batch job, without a terminal, a single file found is used automatically. The file can also be given explicitly:

```bash
python3 gw_analysis.py SIM_DIR --info SIM_DIR/H5/gw_analysis_info.json
```

To add or change the system information later (also in `/gw_info`), without recomputing anything:

```bash
python3 gw_analysis.py --edit-info SIM_DIR/H5/gw_analysis.h5
```

Other options:

| option | |
|---|---|
| `-o FILE` | output file |
| `--radii R1 R2 ...` | use only these extraction radii |
| `--lmax L` | use only modes with l ≤ L |
| `--fcut F` | cut-off frequency of the integration, in Hz |

## Interactive plot (optional)

```bash
python3 gw_plot.py SIM_DIR/H5/gw_analysis.h5
```

It writes `SIM_DIR/H5/gw_analysis.html`, a single page that can be opened in any browser (internet is needed to load Plotly). In the page you can choose:

- the extraction radii (more than one, to compare them);
- the mode;
- ψ₄ or h;
- real part (h₊), imaginary part (h×) or amplitude;
- time as retarded time or from the merger (only if the file has a merger, `has_merger = 1`; for a single NS this option is not shown).

ψ₄ is plotted multiplied by the radius, r·ψ₄, so that different radii can be compared. Each radius has its colour, from deep blue (largest radius) to orange (smallest); the page opens on l2m2 at the largest radius. With all the radii and modes the page is large (about 33 MB for 9 radii, 25 modes and 6768 times). `--radii`, `--lmax` and `--step N` (one point every N) make it smaller. See `python3 gw_plot.py --help`.

## Output file

```
gw_analysis.h5
├── gw_info              summary of the run (text)
├── simulation/          system information (attributes)
├── sampling/            time sampling (attributes), time, time_ms
├── processing/          how h was computed (attributes)
├── units/               conversion factors (attributes)
└── radii/
    ├── R379.73/         one group per extraction radius
    │   ├── tret, tret_ms
    │   ├── l2m-2/psi4_re, psi4_im, rh_plus, rh_cross
    │   ├── l2m-1/ ...   one group per mode (all the l, m written by Multipole)
    │   └── ...
    └── ...
```

All datasets are 1D float arrays. Without suffix the units are code units (G = c = M☉ = 1); `_ms`, `_s`, `_Hz` and `_km` are physical units. `tret` is the retarded time. `rh_plus + 1j*rh_cross` is r·(h₊ + i h×), the same as `rh` in the old `h22.h5` files of pycactus3.

`gw_info` is the summary printed in the terminal at the end of the run: system, ADM mass and angular momentum, Ω₀, output folders, radii, modes, time sampling, frequencies, cut-off frequency and, for binaries, the merger time at every radius. It is updated by `--edit-info`. To read it: `print(f['gw_info'].asstr()[()])`.

**`/simulation`**

| attribute | |
|---|---|
| `system` | BNS, BBH, BHNS or NS |
| `has_merger` | 1 for binaries, 0 for a single NS (no merger time in the file) |
| `Madm`, `Jadm` | initial ADM mass [M☉] and angular momentum [M☉²] |
| `omega0`, `omega0_cu` | initial angular velocity [rad/s], [code units] |
| `f_gw0` | initial GW frequency Ω₀/π [Hz] (binaries) |
| `name`, `description`, `id_code`, `evol_code`, `dx`, `separation`, `notes` | optional |
| `m1`, `m2`, `mb1`, `mb2`, `R1`, `R2`, `Lambda1`, `Lambda2` | BNS, optional [M☉, km] |
| `m_bh1`, `m_bh2`, `chi1`, `chi2` | BBH, optional |
| `m_bh`, `chi_bh`, `m_ns`, `mb_ns`, `R_ns`, `Lambda_ns` | BHNS, optional |
| `m_ns`, `mb_ns`, `R_ns`, `rho_c` | NS, optional [M☉, km, g/cm³] |
| `eos`, `eos_type`, `eos_id`, `eos_evol`, `eos_table`, `gamma_th` | EOS, optional |
| `Mtot`, `q`, `Mchirp`, `C1`, `C2`, `C_ns` | computed from the masses and radii |

**`/sampling`**

| attribute | |
|---|---|
| `N` | number of samples |
| `dt`, `dt_ms`, `dt_s` | time step |
| `t0`, `tf`, `T` (and `_ms`), `T_s` | initial and final time, duration |
| `fs`, `fnyq`, `df` (and `_Hz`) | sampling rate 1/dt, Nyquist frequency 1/(2dt), frequency resolution 1/(N dt) |
| `outputs`, `outputs_t0`, `outputs_tf`, `ndup` | output folders used, their time range, repeated times removed |
| `uniform`, `dt_min`, `dt_max` | check of the time step |

**`/radii/R*`**

| attribute | |
|---|---|
| `R`, `Riso`, `Riso_km` | coordinate radius, areal radius |
| `rstar` | t − tret |
| `t_merg`, `t_merg_ms` | merger time (binaries) |
| `f_merg_Hz`, `A_merg` | GW frequency and \|r·h₂₂\| at the merger |
| `N_post`, `T_post_ms`, `df_post_Hz` | samples, duration and frequency resolution after the merger (binaries) |

**`/processing`**: cut-off frequency `f0` (`f0_Hz`), radii, modes and the routines used.

Example:

```python
import h5py, numpy as np
f = h5py.File('gw_analysis.h5', 'r')
g = f['radii/R1139.18']
t  = g['tret_ms'][:] - g.attrs['t_merg_ms']
hp = g['l2m2/rh_plus'][:] * f['units'].attrs['CU_to_km']            # r*h_plus [km]
freq = np.fft.rfftfreq(len(hp), f['sampling'].attrs['dt_s'])        # [Hz]
```

## How it is computed

The steps are the same as in the old `h22.py` script with pycactus3, at every extraction radius (no extrapolation to infinite radius):

1. the cut-off frequency is f0 = Ω₀/π;
2. psi4 is integrated twice in time, with the integration constants removed by a linear fit and a Butterworth high-pass filter at f0 (`NIntegratePsi4_filter`); then h is multiplied by the areal radius `Riso`;
3. the retarded time is `RetardedTime(t, Riso(R), Madm)`, as in `h22.py`;
4. for binaries, the merger time is the maximum of |r·h₂₂| at that radius (`FindMaximumTimeSeries`). For a single NS there is no merger time.

## Acknowledgments

We thank Roberto De Pietri, Alessandra Feo, Frank Loffler, Francesco Maione and Michele Pasquali for developing the PYCACTUS python post-processing package for analysing output of Einstein Toolkit simulations.

## Copyright

Copyright (C) 2026 Davide Guerra
