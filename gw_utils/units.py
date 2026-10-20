# Copyright (C) 2026 Davide Guerra
#
# Constants and conversion factors, code units G = c = M_sun = 1.
# Same values (LORENE) and same formulas as pycactus3/UtilityUnits.py

G       = 6.6738e-11        # m^3/(kg s^2)
c       = 299792458.0       # m/s
M_sun   = 1.9885e30         # kg
Mparsec = 3.08567758e19     # km

CU_to_s  = (M_sun*G/(c*c*c))     # s
CU_to_m  = M_sun*G/(c*c)         # m
CU_to_km = CU_to_m/1000          # km
CU_to_ms = 1000*CU_to_s          # ms


def as_dict():
    return {'CU_to_s': CU_to_s, 'CU_to_ms': CU_to_ms, 'CU_to_m': CU_to_m, 'CU_to_km': CU_to_km,
            'G': G, 'c': c, 'M_sun': M_sun, 'Mparsec': Mparsec}
