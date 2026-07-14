import os


def pytest_configure(config):
    """Ensure auth is disabled during tests regardless of .env file."""
    os.environ["ADMIN_PASSWORD"] = ""
