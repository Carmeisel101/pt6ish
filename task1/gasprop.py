"""
Pick the gas-properties wrapper that matches this operating system.

winGasProp.py embeds the Windows (Cygwin) build of the course gas-properties
program and macGasProp.py embeds the macOS (x86-64) build. Both expose the same
GasProp class, so the rest of the code imports it from here.
"""
import sys

if sys.platform.startswith('win') or sys.platform == 'cygwin':
    from winGasProp import GasProp
elif sys.platform == 'darwin':
    from macGasProp import GasProp
else:
    raise ImportError(
        'The gas-properties program is only provided as Windows and macOS builds; '
        f'there is no build for {sys.platform}.'
    )

__all__ = ['GasProp']
