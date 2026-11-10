"""
How accurate is the table-based gas-properties fallback (tableGasProp.py)?

Four groups of checks, each against a pass limit fixed in advance:

  1. Point checks: the fallback reproduces the property values the compiled
     program produced for the committed design-point run
     (reference/fortran_results*.csv).
  2. End-to-end: a full Task 1 run on the fallback, in a scratch copy of this
     folder, matches every number in the committed results.
  3. Physics: enthalpy rises with temperature, cp is smooth and plausible,
     T -> h -> T round-trips, and entropy follows the ideal-gas pressure law.
  4. Program sweep: if the compiled program runs on this machine, compare the
     two backends across the whole temperature range. Skipped otherwise.

Run from the task1 folder:   python test_gasprop.py     (or: make test)
Exits with status 1 if any check fails.
"""
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

from tableGasProp import GasProp as TableGasProp

HERE = os.path.dirname(os.path.abspath(__file__))
R = 0.28716
MIN_L = 14.66

# Pass limits, fixed before looking at results
TOL_H_REL = 0.05e-2   # enthalpy, relative
TOL_S_ABS = 0.002     # entropy, kJ/kg-K
TOL_P_REL = 0.5e-2    # pressure derived from (h, s), relative
TOL_E2E_REL = 0.5e-2  # any number in the end-to-end comparison, relative
TOL_SWEEP_H_REL = 0.1e-2
TOL_SWEEP_S_ABS = 0.003

REF = pd.read_csv(os.path.join(HERE, 'reference', 'fortran_results.csv'), index_col=0).set_index('Stage')
REF2 = pd.read_csv(os.path.join(HERE, 'reference', 'fortran_results2.csv'), index_col=0).iloc[0]

failures = []


def report(name, ref, got, ok, detail):
    status = 'PASS' if ok else 'FAIL'
    if not ok:
        failures.append(name)
    print(f'  [{status}] {name:42s} ref {ref:12.5f}   got {got:12.5f}   {detail}')


def check_rel(name, ref, got, tol):
    rel = (got - ref) / ref
    report(name, ref, got, abs(rel) <= tol, f'{100 * rel:+.4f}%  (limit {100 * tol:.3g}%)')


def check_abs(name, ref, got, tol):
    diff = got - ref
    report(name, ref, got, abs(diff) <= tol, f'{diff:+.5f}   (limit {tol:g})')


def air():
    gp = TableGasProp()
    gp.air()
    return gp


def gas(lam):
    gp = TableGasProp()
    gp.combustion(lamb=lam)
    return gp


# ---------------------------------------------------------------------------
def point_checks():
    print('\n1. Point checks against the compiled program (design-point run)')
    H = lambda st: REF.loc[st, 'Enthalpy [kJ/kg]']
    S = lambda st: REF.loc[st, 'Entropy [kJ/kg-K]']
    P = lambda st: REF.loc[st, 'Pressure [bar]']
    lam = REF2['lambda']

    check_rel('air h(T = 288.16 K)              [a]', H('a'), air().h(T=288.16), TOL_H_REL)
    check_abs('air s(T = 288.16 K, p_a)          [a]', S('a'), air().s(T=288.16, p=P('a')), TOL_S_ABS)
    check_rel('air h(s, p) after compression    [2i]', H('02i'),
              air().h(s=S('02i') + R * np.log(P('02i')), p=1), TOL_H_REL)
    check_abs('air s(h, p)                       [2]', S('02'), air().s(h=H('02'), p=P('02')), TOL_S_ABS)
    check_rel(f'gas h(T = TIT), lambda = {lam:.3f}   [3]', H('03'), gas(lam).h(T=REF2['TIT']), TOL_H_REL)
    check_abs('gas s(T = TIT, p3)                [3]', S('03'), gas(lam).s(T=REF2['TIT'], p=P('03')), TOL_S_ABS)
    for st, lab in [('04', '4'), ('045', '4.5')]:
        check_abs(f'gas s(h, p)                      [{lab}]', S(st), gas(lam).s(h=H(st), p=P(st)), TOL_S_ABS)
    for st, lab in [('04i', '4i'), ('045i', '4.5i')]:
        check_rel(f'gas p(h, s)                     [{lab}]', P(st), gas(lam).p(h=H(st), s=S(st)), TOL_P_REL)


# ---------------------------------------------------------------------------
def end_to_end():
    print('\n2. End-to-end: Task 1 on the table fallback vs the committed results')
    with tempfile.TemporaryDirectory() as tmp:
        work = os.path.join(tmp, 'task1')
        shutil.copytree(HERE, work, ignore=shutil.ignore_patterns('__pycache__', 'images', 'GPexe'))
        env = dict(os.environ, GASPROP='tables', MPLBACKEND='Agg')
        run = subprocess.run([sys.executable, 'main.py'], cwd=work, env=env,
                             capture_output=True, text=True)
        if run.returncode != 0:
            failures.append('end-to-end run')
            print('  [FAIL] main.py did not finish:\n' + run.stderr[-2000:])
            return
        new = pd.read_csv(os.path.join(work, 'results.csv'), index_col=0).set_index('Stage')
        new2 = pd.read_csv(os.path.join(work, 'results2.csv'), index_col=0).iloc[0]

    worst = {}
    for col in ['Pressure [bar]', 'Enthalpy [kJ/kg]', 'Entropy [kJ/kg-K]']:
        rel = ((new[col] - REF[col]) / REF[col]).abs()
        st = rel.idxmax()
        worst[col] = (st, REF.loc[st, col], new.loc[st, col])
    for col, (st, ref, got) in worst.items():
        check_rel(f'worst station for {col.split()[0].lower():9s} [{st}]', ref, got, TOL_E2E_REL)
    for key in ['w_c', 'w_t', 'w_PT', 'm_fuel', 'Spec_Thrust', 'EBSFC', 'lambda']:
        check_rel(f'results2: {key}', REF2[key], new2[key], TOL_E2E_REL)


# ---------------------------------------------------------------------------
def physics():
    print('\n3. Physical consistency of the fallback tables')
    for name, gp, T_max in [('air', air(), 1700.0), ('stoich. products', gas(1.0), 1620.0)]:
        T = np.arange(280.0, T_max, 1.0)
        h = np.array([gp.h(T=t) for t in T])
        cp = np.diff(h) / np.diff(T)
        mono = bool(np.all(cp > 0))
        report(f'{name}: h increases with T', 1, float(mono), mono, f'min cp {cp.min():.3f} kJ/kg-K')
        plausible = bool(0.95 < cp[:20].mean() < 1.10 and 1.10 < cp[-20:].mean() < 1.40)
        report(f'{name}: cp plausible at both ends', 1, float(plausible), plausible,
               f'cp ~ {cp[:20].mean():.3f} near 300 K, {cp[-20:].mean():.3f} near {T_max:.0f} K')
        # The tables round h to 0.1 kJ/kg, so cp from 1 K steps jumps by 0.1-0.2
        # just from rounding. Average cp over 10 K instead: a leftover typo of
        # 0.6 kJ/kg (the repair threshold) would move two neighbouring 10 K
        # averages by 0.06 in opposite directions, a step of about 0.12.
        cp10 = (h[10::10] - h[:-10:10]) / 10.0
        jump = np.abs(np.diff(cp10)).max()
        report(f'{name}: cp smooth (no table typos left)', 0, jump, jump < 0.10,
               f'largest step in 10 K-average cp {jump:.3f} (limit 0.10)')
        trip = max(abs(gp.T(h=gp.h(T=t)) - t) for t in T[::25])
        report(f'{name}: T -> h -> T round trip', 0, trip, trip < 0.01, f'max error {trip:.2e} K')
        ds = gp.s(T=900.0, p=5.0) - gp.s(T=900.0, p=1.0)
        report(f'{name}: s(T, 5 bar) - s(T, 1 bar)', -R * np.log(5), ds,
               abs(ds + R * np.log(5)) < 1e-9, 'ideal-gas pressure term')


# ---------------------------------------------------------------------------
def sweep_against_program():
    print('\n4. Sweep against the compiled program')
    import gasprop
    if gasprop.BACKEND != 'fortran':
        print('  [SKIP] the compiled program does not run on this machine')
        return
    prog = gasprop.GasProp
    for name, setup in [('air', lambda g: g.air()), ('stoich. products', lambda g: g.combustion(lamb=1))]:
        a, b = prog(), TableGasProp()
        setup(a)
        setup(b)
        worst_h = worst_s = 0.0
        for t in np.arange(280.0, 1600.0, 20.0):
            worst_h = max(worst_h, abs(b.h(T=t) - a.h(T=t)) / a.h(T=t))
            worst_s = max(worst_s, abs(b.s(T=t, p=1) - a.s(T=t, p=1)))
        report(f'{name}: worst h over 280-1600 K', 0, worst_h, worst_h <= TOL_SWEEP_H_REL,
               f'{100 * worst_h:.4f}% (limit {100 * TOL_SWEEP_H_REL:.2g}%)')
        report(f'{name}: worst s over 280-1600 K', 0, worst_s, worst_s <= TOL_SWEEP_S_ABS,
               f'{worst_s:.5f} (limit {TOL_SWEEP_S_ABS:g})')


if __name__ == '__main__':
    os.chdir(HERE)
    point_checks()
    end_to_end()
    physics()
    sweep_against_program()
    print()
    if failures:
        print(f'{len(failures)} check(s) failed: ' + '; '.join(failures))
        sys.exit(1)
    print('All checks passed.')
