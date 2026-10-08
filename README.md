# An Autonomous Agent for Accelerator Beam Dynamics

This semesterproject is dedicated to creating an autonomous
agent in order to orchestrate the heterogeneous software ecosystem 
for accelerator design and simulation. The framework for this project
will be based on the ColliderAgent architecture. 

## Python environment

Install [uv](https://docs.astral.sh/uv/getting-started/installation/), then run
from this repository:

```bash
uv sync --locked
source .venv/bin/activate
```

This creates a local Python 3.12 environment with the Magnus SDK, NumPy,
SciPy, pandas, matplotlib, and h5py. Python is downloaded if needed.
`pyproject.toml`, `.python-version`, and `uv.lock` describe the environment;
commit these files rather than `.venv`, which is already ignored by Git.
The lockfile records exact dependency versions for subsequent installations.

The SDK connects to the existing Magnus backend using your Magnus configuration:

```bash
magnus config
```

Installing the SDK does not start a backend or register project blueprints.
Docker and the OPALX container are separate simulation requirements.

For development against a local Magnus SDK checkout, optionally replace the
installed SDK (adjust the path for your machine):

```bash
uv pip install --no-deps --editable "$HOME/.magnus/repository/sdks/python"
```

This local override is not part of the reproducible environment. After applying
it, use the activated environment's `python` and `magnus` commands directly;
`uv sync --locked` restores the locked SDK release. The backend configuration
and data are shared across Python environments.
