import shutil
from pathlib import Path

import pytest


@pytest.fixture(scope="session", autouse=True)
def setup_and_teardown():
	"""Create the test directories before all tests and clean up after all tests."""
	temp_path = Path("./tests/temp")
	final_path = Path("./tests/downloads")

	# Create the directories before all tests
	temp_path.mkdir(parents=True, exist_ok=True)
	final_path.mkdir(parents=True, exist_ok=True)

	yield

	# Clean up after all tests
	shutil.rmtree(temp_path, ignore_errors=True)
	shutil.rmtree(final_path, ignore_errors=True)


@pytest.fixture(scope="session")
def test_config():
	"""Load the test configuration."""
	config_path = Path(__file__).parent / "test_config.json"
	return config_path


@pytest.fixture(scope="function")
def temp_download_dir(test_config):
	"""Return the paths for temp and final download directories."""
	config_path = test_config
	config = config_path.read_text()
	import json
	config = json.loads(config)
	final_path = Path(config["final_path"])
	temp_path = Path(config["temp_path"])

	yield final_path, temp_path