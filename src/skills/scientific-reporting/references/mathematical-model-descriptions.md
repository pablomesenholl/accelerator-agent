# Mathematical model descriptions

Use this reference to explain the physics represented by a simulation, including useful analytical approximations. Present established models and available calculations; new model derivations, proxy evaluations, observable calculations, and numerical comparisons belong to the physics or analysis stage.

## 1. Choose the formulation

Choose the representation that helps answer the scientific question:

- **Hamiltonian:** when canonical variables and the relevant Hamiltonian are established for the modeled dynamics.
- **Equations of motion:** when forces, fields, or collective effects are more directly described this way.
- **Transfer matrix or map:** for transport and local linear optics, including linearization around a verified reference or closed orbit.

Use only the detail needed to explain the setup and findings. A Hamiltonian is optional; do not force dissipative or otherwise unsupported effects into a conservative single-particle model.

## 2. Define conventions

State the ordered variables, coordinate frame and reference trajectory, independent variable (such as time $t$ or path length $s$), momentum definitions, normalization, units, and reference energy or momentum. Distinguish canonical momentum from mechanical momentum and particle slopes. Follow the analyzer's [physics conventions](../../beam-analyzer/references/physics-conventions.md) when relating equations to stored diagnostics.

A Hamiltonian generating evolution in $s$ is not automatically the particle's physical energy. Define its convention and scaling explicitly; do not assume that changing the independent variable leaves the Hamiltonian unchanged.

## 3. Connect equations to the configured model

Identify which terms describe the configured elements and effects, and which effects are omitted. State approximations such as linearization, paraxial motion, fixed energy, ideal fields, or neglected collective effects only when applicable. Explain where these assumptions limit interpretation.

Distinguish the continuous physical model from its numerical integration and solver settings. Use the [local OPALX reference](../../lattice-generator/references/opalx-input-reference.md) for configuration semantics before consulting official documentation. An idealized equation does not establish the exact algorithm or Hamiltonian implemented by OPALX.

## 4. Distinguish Hamiltonian, generator, and transfer matrix

For a quadratic model of small deviations about a reference solution, take canonical variables $\boldsymbol{\xi}=(q_1,\ldots,q_n,P_1,\ldots,P_n)^T$ with a consistent canonical normalization. With independent variable $\tau$ and symmetric coefficient matrix $G(\tau)$,

$$
K(\boldsymbol{\xi},\tau)=\tfrac12\boldsymbol{\xi}^T G(\tau)\boldsymbol{\xi},
\qquad
\frac{d\boldsymbol{\xi}}{d\tau}=A(\tau)\boldsymbol{\xi},
\qquad
A=JG,\quad J=\begin{pmatrix}0&I\\-I&0\end{pmatrix}.
$$

The transfer matrix satisfies

$$
\boldsymbol{\xi}(\tau)=M(\tau,\tau_0)\boldsymbol{\xi}(\tau_0),
\qquad \frac{dM}{d\tau}=A(\tau)M,
\qquad M(\tau_0,\tau_0)=I.
$$

Here $G$ specifies the quadratic Hamiltonian, $A$ generates evolution, and $M$ transports deviations over an interval. For constant $A$, $M=\exp[A(\tau-\tau_0)]$; do not apply this simple exponential to a general varying generator. For background on Hamiltonian and matrix formalism, see Y. Papaphilippou, [Particle Motion in Hamiltonian Formalism](https://arxiv.org/abs/2402.16474) (2024), CERN Accelerator School lecture notes. These relations are not an OPALX-specific model. Do not substitute stored mechanical momenta into canonical formulas without establishing the required transformation.

## 5. Use analytical proxies responsibly

A linear-optics or idealized-lattice model can explain trends and provide expectations. State what it predicts, which simulation parameters it uses, and what it omits. Present and interpret existing calculation artifacts with their provenance, labeling proxy predictions separately from simulation measurements. Include existing comparisons only when observables, frames, units, and locations are compatible.

Do not evaluate analytical proxies, calculate new observables, or perform numerical comparisons in the reporting stage. If a useful proxy calculation or comparison is unavailable, identify the missing analysis and its purpose without performing it. Discuss documented discrepancies as evidence requiring interpretation; agreement alone does not validate all simulated physics, and disagreement alone does not identify a numerical defect.

## 6. Evidence and limits

Cite the source and assumptions of each substantive formulation. Claim exact correspondence with OPALX only when verified documentation or implementation evidence supports it. If conventions, required inputs, or a suitable formulation cannot be established, describe the supported physics and explicitly identify the missing mathematical account. Preserve the report's supported content without inventing equations or results.
