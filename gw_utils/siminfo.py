# Copyright (C) 2026 Davide Guerra
#
# Information on the simulated system, asked to the user in the terminal.
# Entries left blank are stored as NaN (numbers) or '' (text).

import json
import math

from . import units as U

SYSTEMS = {
    'BNS': 'binary neutron star',
    'BBH': 'binary black hole',
    'BHNS': 'black hole - neutron star binary',
    'NS': 'single neutron star',
}
ALIASES = {'NSBH': 'BHNS', 'BNSBH': 'BHNS', 'BH-NS': 'BHNS', 'NS-BH': 'BHNS'}
BINARIES = ('BNS', 'BBH', 'BHNS')
WITH_NS = ('BNS', 'BHNS', 'NS')
ALL = tuple(SYSTEMS)

# optional entries: (key, question, type, systems)
OPTIONAL = [
    ('name',        'Simulation name', str, ALL),
    ('description', 'Short description', str, ALL),
    ('id_code',     'Initial data code (LORENE, FUKA, RNS, ...)', str, ALL),
    ('evol_code',   'Evolution code (e.g. ET + GRHayLHD)', str, ALL),
    ('dx',          'Finest grid spacing [code units]', float, ALL),
    ('separation',  'Initial separation [km]', float, BINARIES),
    ('m1',          'NS 1 gravitational mass [M_sun]', float, ('BNS',)),
    ('mb1',         'NS 1 baryon mass [M_sun]', float, ('BNS',)),
    ('R1',          'NS 1 radius [km]', float, ('BNS',)),
    ('Lambda1',     'NS 1 tidal deformability', float, ('BNS',)),
    ('m2',          'NS 2 gravitational mass [M_sun]', float, ('BNS',)),
    ('mb2',         'NS 2 baryon mass [M_sun]', float, ('BNS',)),
    ('R2',          'NS 2 radius [km]', float, ('BNS',)),
    ('Lambda2',     'NS 2 tidal deformability', float, ('BNS',)),
    ('m_bh1',       'BH 1 mass [M_sun]', float, ('BBH',)),
    ('chi1',        'BH 1 dimensionless spin', float, ('BBH',)),
    ('m_bh2',       'BH 2 mass [M_sun]', float, ('BBH',)),
    ('chi2',        'BH 2 dimensionless spin', float, ('BBH',)),
    ('m_bh',        'BH mass [M_sun]', float, ('BHNS',)),
    ('chi_bh',      'BH dimensionless spin', float, ('BHNS',)),
    ('m_ns',        'NS gravitational mass [M_sun]', float, ('BHNS', 'NS')),
    ('mb_ns',       'NS baryon mass [M_sun]', float, ('BHNS', 'NS')),
    ('R_ns',        'NS radius [km]', float, ('BHNS', 'NS')),
    ('Lambda_ns',   'NS tidal deformability', float, ('BHNS',)),
    ('rho_c',       'NS central rest-mass density [g/cm^3]', float, ('NS',)),
    ('eos',         'EOS name', str, WITH_NS),
    ('eos_type',    'EOS type (tabulated, piecewise polytrope, ...)', str, WITH_NS),
    ('eos_id',      'EOS of the initial data', str, WITH_NS),
    ('eos_evol',    'EOS during the evolution', str, WITH_NS),
    ('eos_table',   'EOS table file', str, WITH_NS),
    ('gamma_th',    'Gamma_th (hybrid EOS)', float, WITH_NS),
    ('notes',       'Notes', str, ALL),
]
TEXT = {'system', 'output'} | {k for k, _, typ, _ in OPTIONAL if typ is str}


def optional(system):
    return [o for o in OPTIONAL if system in o[3]]


def blank(typ):
    return '' if typ is str else math.nan


def isblank(x):
    return x is None or x == '' or (isinstance(x, float) and math.isnan(x))


def get_system(s):
    s = str(s).strip().upper()
    names = list(SYSTEMS)
    if s.isdigit() and 1 <= int(s) <= len(names):
        return names[int(s)-1]
    s = ALIASES.get(s, s)
    if s not in SYSTEMS:
        raise ValueError('unknown system %s (BNS, BBH, BHNS or NS)' % s)
    return s


def get_omega(s):
    """'1777.26', '1777.26 rad/s' -> rad/s;  '0.0087 cu' -> code units.
    Without units: >= 1 is rad/s, < 1 is code units. Returns omega in rad/s."""
    s = str(s).strip().lower().replace(' ', '')
    if s.endswith('rad/s'):
        return float(s[:-5])
    if s.endswith('cu'):
        return float(s[:-2])/U.CU_to_s
    w = float(s)
    return w if w >= 1 else w/U.CU_to_s


## questions
def _input(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        raise SystemExit('\nAborted.')


def ask(question, typ=str, default=None, required=False, clear=False):
    """Enter -> default (or blank). With clear=True '-' empties the entry."""
    hint = '' if isblank(default) else ' [%s]' % default
    while True:
        s = _input('  %s%s: ' % (question, hint))
        if clear and s == '-':
            return blank(typ)
        if not s:
            if not isblank(default):
                return default
            if required:
                print('    required')
                continue
            return blank(typ)
        if typ is float:
            try:
                return float(s)
            except ValueError:
                print('    not a number')
                continue
        return s


def ask_yn(question, default=False):
    while True:
        s = _input('  %s %s: ' % (question, '[Y/n]' if default else '[y/N]')).lower()
        if s == '':
            return default
        if s in ('n', 'no'):
            return False
        if s in ('y', 'yes', 's', 'si'):
            return True


def ask_system():
    for i, (k, v) in enumerate(SYSTEMS.items(), 1):
        print('     %d) %-5s %s' % (i, k, v))
    while True:
        try:
            return get_system(ask('System type', str, required=True))
        except ValueError as e:
            print('    %s' % e)


def ask_omega(binary):
    q = 'Initial orbital angular velocity Omega0 [rad/s, or "<value> cu"]'
    if not binary:
        q = 'Angular velocity of the star [rad/s, or "<value> cu"] (Enter to skip)'
    while True:
        s = ask(q, str, required=binary)
        if s == '':
            return math.nan
        try:
            w = get_omega(s)
        except ValueError:
            print('    not a number')
            continue
        print('    Omega0 = %.15g rad/s = %.10g code units' % (w, w*U.CU_to_s))
        return w


def ask_optional(info, edit=False):
    print('  (Enter = keep, "-" = clear)' if edit else '  (Enter to skip)')
    for key, q, typ, _ in optional(info['system']):
        info[key] = ask(q, typ, info.get(key) if edit else None, clear=edit)


def collect(interactive, jsonfile=None):
    """Asks what is missing. jsonfile = answers of a previous run."""
    info = load_json(jsonfile) if jsonfile else {}
    if not isblank(info.get('system')):
        info['system'] = get_system(info['system'])
    binary = info.get('system') in BINARIES

    if interactive:
        if isblank(info.get('system')) or isblank(info.get('Madm')) or 'Jadm' not in info \
                or 'omega0' not in info or (binary and (isblank(info['Jadm']) or isblank(info['omega0']))):
            print('\n--- Simulation')
        if isblank(info.get('system')):
            info['system'] = ask_system()
            binary = info['system'] in BINARIES
        if isblank(info.get('Madm')):
            info['Madm'] = ask('Initial ADM mass [M_sun]', float, required=True)
        if 'Jadm' not in info or (binary and isblank(info['Jadm'])):
            q = 'Initial ADM angular momentum [M_sun^2]'
            info['Jadm'] = ask(q if binary else q + ' (Enter to skip)', float, required=binary)
        if 'omega0' not in info or (binary and isblank(info['omega0'])):
            info['omega0'] = ask_omega(binary)
        if any(o[0] not in info for o in optional(info['system'])):
            print('\n--- Other information (optional)')
            if ask_yn('Add information on the system (name, masses, radii, EOS, ...)?'):
                ask_optional(info)
    else:
        need = ['system', 'Madm'] + (['Jadm', 'omega0'] if binary else [])
        miss = [k for k in need if isblank(info.get(k))]
        if miss:
            raise SystemExit('ERROR: missing %s. Run in a terminal to answer the questions, '
                             'or use --info FILE.json' % ', '.join(miss))

    info.setdefault('Jadm', math.nan)
    info.setdefault('omega0', math.nan)
    for key, _, typ, _ in optional(info['system']):
        info.setdefault(key, blank(typ))
    return info


## attributes of /simulation
def sim_attrs(info):
    system = info['system']
    w = float(info['omega0'])
    a = {'system': system, 'system_long': SYSTEMS[system],
         'has_merger': int(system in BINARIES),      # 0 for a single NS: no merger time in the file
         'Madm': float(info['Madm']), 'Jadm': float(info['Jadm']),
         'omega0': w, 'omega0_cu': w*U.CU_to_s}
    if system in BINARIES:
        a['f_gw0'] = w/math.pi
    for key, _, typ, _ in optional(system):
        a[key] = info.get(key, blank(typ))
    a.update(derived(info))
    return a


def derived(info):
    """total mass, mass ratio, chirp mass and compactness, when the masses are given"""
    g = lambda k: math.nan if isblank(info.get(k)) else float(info[k])
    C = lambda m, R: m*U.CU_to_km/R
    system = info['system']
    out = {}
    if system == 'NS':
        out['C_ns'] = C(g('m_ns'), g('R_ns'))
        return out
    if system == 'BNS':
        m1, m2 = g('m1'), g('m2')
        out['C1'], out['C2'] = C(m1, g('R1')), C(m2, g('R2'))
    elif system == 'BHNS':
        m1, m2 = g('m_bh'), g('m_ns')
        out['C_ns'] = C(m2, g('R_ns'))
    else:
        m1, m2 = g('m_bh1'), g('m_bh2')
    M = m1 + m2
    out['Mtot'] = M
    out['q'] = min(m1, m2)/max(m1, m2) if M == M else math.nan
    out['Mchirp'] = (m1*m2)**0.6/M**0.2 if M == M else math.nan
    return out


## answers saved in a json file
def save_json(fname, info):
    with open(fname, 'w') as f:
        json.dump({k: None if isblank(v) else v for k, v in info.items()}, f, indent=2)
        f.write('\n')


def load_json(fname):
    with open(fname) as f:
        raw = json.load(f)
    return {k: (('' if k in TEXT else math.nan) if v is None else v) for k, v in raw.items()}
