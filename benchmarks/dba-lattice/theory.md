# Theory for dba-lattice

Use [cell.json](cell.json) for the element parameters. The model uses ideal hard-edge magnets and paraxial motion.

## Coordinates and reference particle

The independent variable is the reference arc length $s$ in metres. A prime denotes $d/ds$. The three canonical pairs are ordered as

$$
\mathbf u=(x,p_x,y,p_y,\zeta,\eta)^\mathsf T,\qquad
p_x=\frac{P_x}{p_0},\qquad p_y=\frac{P_y}{p_0}.
$$

The local horizontal coordinate $x$ points outward in a bend, and $y$ is vertical. Both are measured in metres. In the ideal-magnet gauge the transverse vector potential vanishes, so $p_x$ and $p_y$ equal the transverse slopes to linear order.

For reference kinetic energy $T_0$ and proton mass $m_p$,

$$
E_0=m_pc^2+T_0,\qquad
\gamma_0=\frac{E_0}{m_pc^2},\qquad
\beta_0=\sqrt{1-\gamma_0^{-2}},\qquad
p_0=\beta_0\gamma_0m_pc.
$$

With particle arrival time $t$ and total energy $E$,

$$
\zeta=s-\beta_0ct,\qquad
\eta=\frac{E-E_0}{\beta_0^2E_0}
     =\frac{\Delta p}{p_0}+\mathcal O\!\left((\Delta p/p_0)^2\right).
$$

The coordinate $\zeta$ is a length and is positive for early arrival. The dimensionless coordinate $\eta$ vanishes for the on-momentum reference particle.

## Zero-current Hamiltonian

For element curvature $h$ in $\mathrm{m^{-1}}$ and physical focusing coefficients $k_x,k_y$ in $\mathrm{m^{-2}}$, use the scaled Hamiltonian

$$
H_{\mathrm{ext}}=
\frac{p_x^2+p_y^2}{2}
+\frac{k_xx^2+k_yy^2}{2}
-hx\eta+\frac{\eta^2}{2\gamma_0^2}.
$$

The coefficients are constant within each element. The canonical state is continuous across element boundaries.
