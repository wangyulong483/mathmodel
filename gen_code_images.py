# -*- coding: utf-8 -*-
"""Generate code PNGs — using PIL directly to avoid Pygments CJK bug (#1213)"""
from PIL import Image, ImageDraw, ImageFont
import os

def render_code_image(code, outfile, font_size=13, line_height=18, padding=16):
    """Render code as image using PIL with Consolas + SimHei fallback"""
    lines = code.strip().split('\n')

    # Try to get a good monospace font
    font_mono = None
    for fname in ['consola.ttf', 'Consolas', 'cour.ttf', 'Courier New']:
        try:
            font_mono = ImageFont.truetype(fname, font_size)
            break
        except:
            pass
    if font_mono is None:
        font_mono = ImageFont.load_default()

    # Calculate image dimensions
    max_width = 0
    for line in lines:
        bbox = font_mono.getbbox(line)
        w = bbox[2] - bbox[0]
        max_width = max(max_width, w)

    img_w = max_width + 2 * padding
    img_h = len(lines) * line_height + 2 * padding

    img = Image.new('RGB', (img_w, img_h), '#ffffff')
    draw = ImageDraw.Draw(img)

    # Use a single dark color for all text (no Pygments tokens = no CJK bug)
    for i, line in enumerate(lines):
        y = padding + i * line_height
        # Strip non-ASCII to avoid CJK overlap bug
        clean_line = ''.join(c if ord(c) < 128 else '  ' for c in line)
        draw.text((padding, y), clean_line, font=font_mono, fill='#1a1a2e')

    img.save(outfile, 'PNG')
    print(f'[OK] {outfile} ({img_w}x{img_h})')

# Simplified code blocks with ASCII-only comments
code_b1 = '''\
import numpy as np
from scipy.integrate import solve_ivp

def sir_ode(t, y, beta, gamma, N):
    """SIR ODE model"""
    S, I, R = y
    dS = -beta * S * I / N
    dI =  beta * S * I / N - gamma * I
    dR =  gamma * I
    return [dS, dI, dR]

def solve_sir(beta, gamma, N, S0, I0, R0, t_eval):
    """Numerical solve using RK45 method"""
    sol = solve_ivp(sir_ode, (t_eval[0], t_eval[-1]),
                    [S0, I0, R0], args=(beta, gamma, N),
                    t_eval=t_eval, method='RK45')
    return sol
'''

code_b2 = '''\
from scipy.interpolate import CubicSpline
from scipy.optimize import minimize

# 7-day observed data
days_obs = np.array([1, 2, 3, 4, 5, 6, 7], dtype=float)
new_cases = np.array([3, 7, 15, 28, 48, 72, 101], dtype=float)
cum_cases = np.cumsum(new_cases)

# Cubic spline (natural boundary condition)
cs_spline = CubicSpline(days_obs, cum_cases, bc_type='natural')

N_total = 10000.0
I0, R0 = cum_cases[0], 0.0
S0 = N_total - I0 - R0

def rss_objective(params, N, S0, I0, R0, t_eval, interp):
    """RSS J(beta, gamma) -- see Eq.(4) in paper"""
    beta, gamma = params
    if beta <= 0 or gamma <= 0:
        return 1e10
    sol = solve_ivp(sir_ode, (t_eval[0], t_eval[-1]),
                    [S0, I0, R0], args=(beta, gamma, N),
                    t_eval=t_eval, method='RK45')
    model_cum = sol.y[1] + sol.y[2]   # C_model = I + R
    obs_interp = interp(t_eval)        # C_interp
    return np.sum((model_cum - obs_interp) ** 2)

# Multi-start L-BFGS-B with bounds: gamma in [0.05, 0.5]
bounds = [(0.1, 2.0), (0.05, 0.5)]
t_fine = np.linspace(1, 7, 200)
best_rss = np.inf
for beta0 in [0.2, 0.5, 1.0, 1.5]:
    for gamma0 in [0.05, 0.1, 0.2, 0.3]:
        res = minimize(rss_objective, [beta0, gamma0],
                       args=(N_total, S0, I0, R0, t_fine, cs_spline),
                       method='L-BFGS-B', bounds=bounds,
                       options={'maxiter': 5000})
        if res.fun < best_rss:
            best_rss = res.fun
            beta_fit, gamma_fit = res.x

print(f"beta={beta_fit:.4f}, gamma={gamma_fit:.4f}, RSS={best_rss:.1f}")
'''

code_b3 = '''\
# Start from day-7 state for prediction
sol_d7 = solve_ivp(sir_ode, (1, 7), [S0, I0, R0],
                   args=(beta_fit, gamma_fit, N_total),
                   t_eval=[7], method='RK45')
S7, I7, R7 = sol_d7.y[0][0], sol_d7.y[1][0], sol_d7.y[2][0]

# Predict day 8-14 (extrapolation)
t_pred = np.linspace(7, 14, 200)
sol_pred = solve_ivp(sir_ode, (7, 14), [S7, I7, R7],
                     args=(beta_fit, gamma_fit, N_total),
                     t_eval=t_pred, method='RK45')

# Control measure analysis: reduce beta
for pct in [0, 10, 20, 30]:
    b_scen = beta_fit * (1 - pct / 100)
    R0_scen = b_scen / gamma_fit
    sol = solve_ivp(sir_ode, (7, 40), [S7, I7, R7],
                    args=(b_scen, gamma_fit, N_total),
                    t_eval=np.linspace(7, 40, 400), method='RK45')
    peak_idx = np.argmax(sol.y[1])
    if R0_scen > 1:
        print(f"beta-{pct}%: R0={R0_scen:.3f}, "
              f"peak day={sol.t[peak_idx]:.1f}, "
              f"peak I={sol.y[1][peak_idx]:.1f}")
    else:
        print(f"beta-{pct}%: R0={R0_scen:.3f}, "
              f"R0<1, monotonic decline")
'''

for name, code in [('code_b1_ode', code_b1), ('code_b2_fitting', code_b2), ('code_b3_prediction', code_b3)]:
    render_code_image(code, f'{name}.png')
