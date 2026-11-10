"""
Table-based stand-in for the course gas-properties program.

Same interface as winGasProp.GasProp / macGasProp.GasProp, but every property
comes from the tabulated values in air_tab.csv (air) and stoich_tab.csv
(stoichiometric combustion products). Combustion products with excess air
lambda are treated the way the course method does: a mass-weighted mix of
stoichiometric products (weight r) and air (weight q = 1 - r), with
r = (1 + minL) / (1 + lambda * minL).

gasprop.py uses this only when the compiled program cannot run.
test_gasprop.py measures how closely it matches the program.

Units match the program: T in K, h in kJ/kg, s in kJ/kg-K, p in bar.
"""
import os

import numpy as np
import pandas as pd

_HERE = os.path.dirname(os.path.abspath(__file__))


def _repair_typos(T, h, limit=0.6, reach=6, window=21):
    """
    Replace entries that sit off the smooth h(T) curve.

    Each point is predicted from each of its `reach` nearest neighbours on
    either side, carrying the neighbour's value along a robust local slope
    (the rolling median of dh/dT over `window` rows), and the median of those
    predictions is taken. A typo, or a short run of them, spoils only a few of
    the predictions, so the median still follows the true curve. Points more
    than `limit` kJ/kg off their prediction (about 6x the table's 0.1 kJ/kg
    rounding) are replaced by a prediction made from good neighbours only.
    """
    n = len(h)
    dT = np.diff(T)
    slope = pd.Series(np.diff(h) / dT).rolling(window, center=True, min_periods=1).median().to_numpy()
    C = np.concatenate([[0.0], np.cumsum(slope * dT)])   # robust integral of dh/dT

    def predict(valid):
        preds = np.full((n, 2 * reach), np.nan)
        idx = np.arange(n)
        for col, k in enumerate([*range(1, reach + 1), *range(-reach, 0)]):
            j = idx - k
            ok = (j >= 0) & (j < n)
            jj = np.clip(j, 0, n - 1)
            ok &= valid[jj]
            preds[ok, col] = h[jj[ok]] + C[idx[ok]] - C[jj[ok]]
        return np.nanmedian(preds, axis=1)

    bad = np.abs(h - predict(np.ones(n, bool))) > limit
    out = h.copy()
    out[bad] = predict(~bad)[bad]
    return out


def load_table(path):
    """
    Load a gas table (T [K], h [kJ/kg], s at 1 bar [kJ/kg-K]).

    The CSV tables were transcribed by hand, so a few enthalpy entries contain
    typos (single entries and short runs, e.g. 1656.3 for 1956.3) and
    air_tab.csv only lists entropy up to 473 K. Typos in h are repaired by
    interpolating across them, and s(T) is rebuilt from the cleaned h via
    ds = dh / T (exact for an ideal gas at constant pressure), anchored to the
    first tabulated entropy value.
    """
    tab = pd.read_csv(path, index_col=0).rename(columns=lambda c: c.strip())
    tab = tab.dropna(subset=['T', 'h']).reset_index(drop=True)
    T, h = tab['T'].to_numpy(), tab['h'].to_numpy(copy=True)
    h = _repair_typos(T, h)
    tab['h'] = h
    T_mid = 0.5 * (T[1:] + T[:-1])
    tab['s'] = tab['s'].iloc[0] + np.concatenate([[0.0], np.cumsum(np.diff(h) / T_mid)])
    return tab


_AIR = load_table(os.path.join(_HERE, 'air_tab.csv'))
_STOICH = load_table(os.path.join(_HERE, 'stoich_tab.csv'))

# Temperature grid on which both tables are defined (1 K spacing)
_T_COMMON = _STOICH['T'].to_numpy()
_T_COMMON = _T_COMMON[_T_COMMON <= _AIR['T'].max()]


def _on_grid(tab, col, T_grid):
    return np.interp(T_grid, tab['T'], tab[col])


class GasProp:

    def __init__(self):
        self._gas_type = 0
        self._xlambda = None
        self._xminl = 14.66
        self._r = 0.28716

    def air(self, r=0.28716):
        self._gas_type = 0
        self._r = r

    def combustion(self, r=0.28716, xminl=14.66, lamb=None, phi=None):
        if lamb is not None and phi is not None:
            raise Exception(f"Please specify only Phi({phi}) or Lambda({lamb})")
        if lamb is None and phi is None:
            raise Exception(f"Please specify Phi({phi}) or Lambda({lamb})")
        self._gas_type = 1
        self._r = r
        self._xminl = xminl
        self._xlambda = lamb if lamb is not None else 1 / phi

    # ------------------------------------------------------------ gas model
    def _table(self):
        """Return (T, h, s at 1 bar) arrays for the current gas."""
        if self._gas_type == 0:
            return _AIR['T'].to_numpy(), _AIR['h'].to_numpy(), _AIR['s'].to_numpy()
        lam, minl = self._xlambda, self._xminl
        if lam < 1:
            raise ValueError(f'tableGasProp only covers lean or stoichiometric mixtures (lambda >= 1), got {lam}')
        w_st = (1 + minl) / (1 + lam * minl)
        w_air = 1 - w_st
        T = _T_COMMON
        h = w_st * _on_grid(_STOICH, 'h', T) + w_air * _on_grid(_AIR, 'h', T)
        s = w_st * _on_grid(_STOICH, 's', T) + w_air * _on_grid(_AIR, 's', T)
        return T, h, s

    @staticmethod
    def _lookup(x, xs, ys, name):
        if not xs[0] <= x <= xs[-1]:
            raise ValueError(f'{name} = {x} is outside the gas table range [{xs[0]:.4g}, {xs[-1]:.4g}]')
        return float(np.interp(x, xs, ys))

    def _s0_from_sp(self, s, p):
        """Entropy at 1 bar for a state given at pressure p."""
        return s + self._r * np.log(p)

    # ------------------------------------------------------------ interface
    def T(self, h=None, p=None, s=None):
        if h is None and p is None and s is None:
            raise Exception("Please specify h or (p and s)")
        if h is not None and (p is not None or s is not None):
            raise Exception("Please specify only h or (p and s)")
        if h is None and (p is None or s is None):
            raise Exception("Please specify p and s")
        T, hh, ss = self._table()
        if h is not None:
            return self._lookup(h, hh, T, 'h')
        return self._lookup(self._s0_from_sp(s, p), ss, T, 's')

    def h(self, T=None, p=None, s=None):
        if T is None and p is None and s is None:
            raise Exception("Please specify T or (p and s)")
        if T is not None and (p is not None or s is not None):
            raise Exception("Please specify only T or (p and s)")
        if T is None and (p is None or s is None):
            raise Exception("Please specify p and s")
        TT, hh, ss = self._table()
        if T is not None:
            return self._lookup(T, TT, hh, 'T')
        return float(np.interp(self.T(p=p, s=s), TT, hh))

    def p(self, T=None, h=None, s=None):
        if s is None:
            raise Exception("Please specify (T and s) or (h and s)")
        if T is None and h is None:
            raise Exception("Please specify T or h")
        TT, hh, ss = self._table()
        if T is None:
            T = self.T(h=h)
        s0 = self._lookup(T, TT, ss, 'T')
        return float(np.exp((s0 - s) / self._r))

    def s(self, T=None, h=None, p=None):
        if p is None:
            raise Exception("Please specify (T and p) or (h and p)")
        if T is None and h is None:
            raise Exception("Please specify T or h")
        TT, hh, ss = self._table()
        if T is None:
            T = self.T(h=h)
        return self._lookup(T, TT, ss, 'T') - self._r * np.log(p)
