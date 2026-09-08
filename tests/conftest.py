import pytest

from strucnode import i18n
from tests import tk_stub

# Installed before any test module imports a UI module. Unconditional on
# purpose: a CI runner ships Tkinter but no display, and deferring to the real
# one there fails every widget test with "no display name".
tk_stub.install()


@pytest.fixture(autouse=True)
def english_locale():
    """Every test starts from a known locale."""
    i18n.set_locale("en")
    yield
    i18n.set_locale("en")
