import pytest

from strucnode import i18n


@pytest.fixture(autouse=True)
def english_locale():
    """Every test starts from a known locale."""
    i18n.set_locale("en")
    yield
    i18n.set_locale("en")
