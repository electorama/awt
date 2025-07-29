import os
import pytest

@pytest.fixture(scope="session")
def awt_dir():
    """Return the absolute path to the awt project root."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
