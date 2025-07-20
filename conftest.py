"""
Pytest configuration and hooks for AWT tests.
"""

def pytest_terminal_summary(terminalreporter, exitstatus, config):
    """
    Called at the end of the test session to display additional information.
    This is where we can show tips about the AWT_PYTEST_CACHING environment variable.
    """
    import os

    caching_backend = os.environ.get('AWT_PYTEST_CACHING', 'none')
    if caching_backend == 'none':
        terminalreporter.write_line("")
        terminalreporter.write_line("TIP: Set AWT_PYTEST_CACHING=filesystem to run tests faster with persistent caching", yellow=True)
        terminalreporter.write_line("     Example: AWT_PYTEST_CACHING=filesystem pytest test_awt_routes.py", yellow=True)
    else:
        terminalreporter.write_line("")
        terminalreporter.write_line(f"AWT_PYTEST_CACHING: {caching_backend}", yellow=True)
