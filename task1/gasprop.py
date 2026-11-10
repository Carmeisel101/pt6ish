"""
Choose the gas-properties backend for Task 1.

  * The course's compiled gas-properties program, through winGasProp.py
    (Windows) or macGasProp.py (macOS x86-64). This is what produced the
    committed results.
  * tableGasProp.py, a pure-Python fallback built on air_tab.csv and
    stoich_tab.csv, used when the program cannot run on this machine.
    test_gasprop.py measures how closely it matches the program.

Set the environment variable GASPROP to force a backend:
    GASPROP=fortran   always use the compiled program (fail if it cannot run)
    GASPROP=tables    always use the table fallback
    GASPROP=auto      (default) use the program if it runs, else the tables
"""
import os
import sys


def _fortran_class():
    if sys.platform.startswith('win') or sys.platform == 'cygwin':
        from winGasProp import GasProp as cls
    elif sys.platform == 'darwin':
        from macGasProp import GasProp as cls
    else:
        raise ImportError(f'no build of the gas-properties program for {sys.platform}')
    return cls


def _fortran_runs(cls):
    """Run one cheap query, hiding the loader's error output if it fails."""
    sys.stdout.flush()
    sys.stderr.flush()
    saved = os.dup(2)
    try:
        with open(os.devnull, 'w') as devnull:
            os.dup2(devnull.fileno(), 2)
            value = cls().h(T=300.0)
        return abs(value - 300.0) < 5.0
    except Exception:
        return False
    finally:
        os.dup2(saved, 2)
        os.close(saved)


def _select():
    choice = os.environ.get('GASPROP', 'auto').lower()
    if choice not in ('auto', 'fortran', 'tables'):
        raise ValueError(f"GASPROP must be 'auto', 'fortran' or 'tables', not {choice!r}")

    if choice != 'tables':
        try:
            cls = _fortran_class()
            if _fortran_runs(cls):
                return cls, 'fortran'
            reason = 'the compiled program did not run on this machine'
        except ImportError as exc:
            reason = str(exc)
        if choice == 'fortran':
            raise RuntimeError(f'GASPROP=fortran, but {reason}')
        print(f'[gasprop] {reason}; using the table-based fallback (tableGasProp.py). '
              'Results will differ slightly from the committed ones; see test_gasprop.py.',
              file=sys.stderr)

    from tableGasProp import GasProp as cls
    return cls, 'tables'


GasProp, BACKEND = _select()

__all__ = ['GasProp', 'BACKEND']
