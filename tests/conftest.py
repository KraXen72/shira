import shutil
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def test_config():
    """Load the test configuration."""
    config_path = Path(__file__).parent / "test_config.json"
    return config_path

@pytest.fixture(scope="function")
def temp_download_dir(test_config):
    """Create a temporary directory for downloads and clean up after the test."""
    final_path = Path("./tests/downloads")
    temp_path = Path("./tests/temp")

    # Ensure the directories exist
    final_path.mkdir(parents=True, exist_ok=True)
    temp_path.mkdir(parents=True, exist_ok=True)

    yield final_path, temp_path

    # Clean up after the test
    shutil.rmtree(final_path, ignore_errors=True)
    shutil.rmtree(temp_path, ignore_errors=True)