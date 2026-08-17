"""Root conftest: stabilises namespace resolution for pytest.

`app/config.py` inserts `backend/dolphin` at sys.path[0] (so the legacy
`common.*` / `dolphin.*` research modules import from scripts). If that
happens before the `dolphin` namespace package is created, Python binds it to
the NESTED `backend/dolphin/dolphin` (Django) package and `dolphin.ml_service`
etc. become unimportable. Importing `dolphin` here first (with the backend
root already on sys.path via `pythonpath` in pyproject.toml) pins the correct
resolution regardless of test collection order.
"""

import dolphin  # noqa: F401
import dolphin.ml_service  # noqa: F401  (cheap: numpy/pandas already cached)