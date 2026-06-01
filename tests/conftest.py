import pytest


# Ensures pytest-asyncio works without decorator on every test
def pytest_configure(config):
    config.addinivalue_line("markers", "asyncio: mark test as async")
