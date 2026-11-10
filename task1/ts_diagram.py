"""
T-s diagram of the PT6A-114 design-point cycle.

Reads the station results written by main.py (results.csv, results2.csv) and the
air / stoichiometric-products gas tables, and draws the real cycle on a T-s chart
with the ideal (isentropic) processes and constant-pressure lines.

Run from the task1 folder:
    python ts_diagram.py
Writes images/Ts_diagram.png (and shows the plot).
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from tableGasProp import load_table  # cleaned air / combustion-product tables

R_AIR = 0.28716  # kJ/kg-K, same constant used throughout stages.py
MIN_L = 14.66    # stoichiometric air/fuel ratio


air = load_table('air_tab.csv')
stoich = load_table('stoich_tab.csv')

# Common temperature grid covered by both tables
T_grid = np.arange(max(air['T'].min(), stoich['T'].min()),
                   min(air['T'].max(), stoich['T'].max()), 1.0)


def prop(tab, col, T):
    return np.interp(T, tab['T'], tab[col])


results = pd.read_csv('results.csv', index_col=0).set_index('Stage')
cycle = pd.read_csv('results2.csv', index_col=0).iloc[0]

lam = cycle['lambda']
r = (1 + MIN_L) / (1 + lam * MIN_L)   # weight of stoichiometric products
q = 1 - r                              # weight of excess air


# Gas models: s(T, p[bar]) and h(T) for air and for combustion products
def h_air(T):
    return prop(air, 'h', T)


def s_air(T, p):
    return prop(air, 's', T) - R_AIR * np.log(p)


def h_gas(T):
    return r * prop(stoich, 'h', T) + q * prop(air, 'h', T)


def s_gas(T, p):
    return r * prop(stoich, 's', T) + q * prop(air, 's', T) - R_AIR * np.log(p)


def T_from_h(h, h_fn):
    return float(np.interp(h, h_fn(T_grid), T_grid))


AIR_STATIONS = ['01', '02i', '02']
GAS_STATIONS = ['03', '04i', '04', '045i', '045', '5']

T = {}
for st in AIR_STATIONS:
    T[st] = T_from_h(results.loc[st, 'Enthalpy [kJ/kg]'], h_air)
for st in GAS_STATIONS:
    T[st] = T_from_h(results.loc[st, 'Enthalpy [kJ/kg]'], h_gas)
s = {st: results.loc[st, 'Entropy [kJ/kg-K]'] for st in AIR_STATIONS + GAS_STATIONS}
p = {st: results.loc[st, 'Pressure [bar]'] for st in AIR_STATIONS + GAS_STATIONS}

# ---------------------------------------------------------------- plotting
plt.rcParams.update({
    'font.family': 'DejaVu Sans',
    'font.size': 11,
    'axes.spines.top': False,
    'axes.spines.right': False,
    'axes.grid': True,
    'grid.alpha': 0.25,
})
C_ACTUAL = '#c0392b'
C_IDEAL = '#7f8c8d'
C_ISOBAR = '#2e86c1'

fig, ax = plt.subplots(figsize=(10, 7), dpi=150)

# Axis window (set first so isobar labels can sit at the visible end of each line)
S_MIN, S_MAX = min(s.values()) - 0.12, max(s.values()) + 0.22
T_MIN, T_MAX = 260, T['03'] + 120
ax.set_xlim(S_MIN, S_MAX)
ax.set_ylim(T_MIN, T_MAX)

# Isobars: air up to the burner, combustion products after it.
# (name, pressure, gas model, T range, label offset in points)
isobars = [
    ('p1', p['01'], 'air', (275, 650), (-4, 8)),
    ('p2', p['02'], 'air', (275, 640), (-6, 10)),
    ('p3', p['03'], 'gas', (700, 1520), (4, 0)),
    ('p4', p['04'], 'gas', (700, 1520), (4, 0)),
    ('p4.5', p['045'], 'gas', (700, 1520), (4, 0)),
]
for name, pb, gas, (t0, t1), off in isobars:
    Tr = np.linspace(t0, t1, 300)
    sr = s_air(Tr, pb) if gas == 'air' else s_gas(Tr, pb)
    ax.plot(sr, Tr, color=C_ISOBAR, lw=0.8, alpha=0.45, zorder=1)
    inside = np.where((sr <= S_MAX) & (Tr <= T_MAX))[0][-1]
    ax.annotate(f'{name} = {pb:.2f} bar', (sr[inside], Tr[inside]), xytext=off,
                textcoords='offset points', color=C_ISOBAR, fontsize=8,
                ha='right' if off[0] < 0 else 'left', va='center',
                annotation_clip=False)


def segment(a, b, **kw):
    ax.plot([s[a], s[b]], [T[a], T[b]], **kw)


# Ideal (isentropic) processes
for a, b in [('01', '02i'), ('03', '04i'), ('04', '045i'), ('045', '5')]:
    segment(a, b, color=C_IDEAL, ls='--', lw=1.3, zorder=2)

# Actual compression and expansions
for a, b in [('01', '02'), ('03', '04'), ('04', '045'), ('045', '5')]:
    segment(a, b, color=C_ACTUAL, lw=2.4, zorder=3)

# Heat addition 02 -> 03: follow the shape of the combustor isobar between the end states
Tb = np.linspace(T['02'], T['03'], 120)
pb = np.linspace(p['02'], p['03'], 120)
sb = s_gas(Tb, pb)
sb = sb + (s['02'] - sb[0]) * (1 - (Tb - Tb[0]) / (Tb[-1] - Tb[0])) \
        + (s['03'] - sb[-1]) * ((Tb - Tb[0]) / (Tb[-1] - Tb[0]))
ax.plot(sb, Tb, color=C_ACTUAL, lw=2.4, zorder=3)

# Exhaust back to ambient (open cycle, heat rejected to atmosphere)
Tr = np.linspace(T['5'], T['01'], 120)
sr = s_air(Tr, p['01'])
sr = sr + (s['5'] - sr[0]) * (1 - (Tr - Tr[0]) / (Tr[-1] - Tr[0])) \
        + (s['01'] - sr[-1]) * ((Tr - Tr[0]) / (Tr[-1] - Tr[0]))
ax.plot(sr, Tr, color=C_ACTUAL, lw=1.2, ls=':', zorder=2)

# Station markers and labels
labels = {
    '01': ('1', (-14, -4)), '02i': ('2i', (-22, 2)), '02': ('2', (8, -6)),
    '03': ('3', (8, 0)), '04i': ('4i', (-24, -4)), '04': ('4', (8, 0)),
    '045i': ('4.5i', (-34, -4)), '045': ('4.5', (8, 0)), '5': ('5', (8, -4)),
}
for st, (lab, off) in labels.items():
    ideal = st.endswith('i')
    ax.scatter(s[st], T[st], s=28 if ideal else 46, zorder=4,
               color='white' if ideal else C_ACTUAL,
               edgecolor=C_IDEAL if ideal else C_ACTUAL, linewidth=1.4)
    ax.annotate(lab, (s[st], T[st]), xytext=off, textcoords='offset points',
                fontsize=10, fontweight='normal' if ideal else 'bold')


def process_note(a, b, text, off):
    sm, Tm = (s[a] + s[b]) / 2, (T[a] + T[b]) / 2
    ax.annotate(text, (sm, Tm), xytext=off, textcoords='offset points',
                fontsize=9, color='#34495e', ha='left')


process_note('01', '02', f"Compressor\nw$_c$ = {cycle['w_c']:.0f} kJ/kg", (10, -10))
process_note('02', '03', f"Combustor\nTIT = {cycle['TIT']:.0f} K, λ = {lam:.2f}", (-150, 0))
process_note('03', '04', f"Compressor turbine\nw$_t$ = {cycle['w_t']:.0f} kJ/kg", (12, 0))
process_note('04', '045', f"Power turbine\nw$_{{PT}}$ = {cycle['w_PT']:.0f} kJ/kg", (12, -6))
process_note('045', '5', 'Exhaust nozzle\n(to ambient)', (12, -10))

ax.set_xlabel('Specific entropy  s  [kJ/kg·K]')
ax.set_ylabel('Temperature  T  [K]')
ax.set_title('PT6A-114 design-point cycle on the T–s plane', fontsize=13, pad=12)

from matplotlib.lines import Line2D
ax.legend(handles=[
    Line2D([], [], color=C_ACTUAL, lw=2.4, label='Actual process'),
    Line2D([], [], color=C_IDEAL, lw=1.3, ls='--', label='Isentropic (ideal)'),
    Line2D([], [], color=C_ISOBAR, lw=0.8, alpha=0.6, label='Constant pressure'),
], loc='upper left', frameon=False)

fig.tight_layout()
fig.savefig('images/Ts_diagram.png', dpi=200, bbox_inches='tight', facecolor='white')
print({k: round(v, 1) for k, v in T.items()})
plt.show()
