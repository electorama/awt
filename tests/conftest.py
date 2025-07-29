"""
Pytest configuration and hooks for AWT tests.
"""
import os
import pytest

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """
    Called at the end of the test session to display additional information.
    This is where we can show tips about the AWT_PYTEST_CACHING environment variable.
    """

    caching_backend = os.environ.get('AWT_PYTEST_CACHING', 'none')
    if caching_backend == 'none':
        terminalreporter.write_line("")
        terminalreporter.write_line("TIP: Set AWT_PYTEST_CACHING=filesystem to run tests faster with persistent caching", yellow=True)
        terminalreporter.write_line("     Example: AWT_PYTEST_CACHING=filesystem pytest test_awt_routes.py", yellow=True)
    else:
        terminalreporter.write_line("")
        terminalreporter.write_line(f"AWT_PYTEST_CACHING: {caching_backend}", yellow=True)

@pytest.fixture(scope="session")
def awt_dir():
    """Return the absolute path to the awt project root."""
    return os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
