"""Integration tests require a running dev server — skip under pytest.

These smoke tests are standalone scripts (run with `python` against
localhost:8000/8001/5173). Their test functions take `client: httpx.Client`
as a plain parameter, not a pytest fixture.
"""

collect_ignore_glob = ["*.py"]
