import shutil
import sys

import pytest
import requests_cache
from test_harness import DOWNLOADS_DIR


@pytest.hookimpl(trylast=True)
def pytest_runtest_logstart(nodeid, location):
	"""Insert a newline after pytest prints the test name, so CLI output starts on a new line."""
	sys.stdout.write("\n")
	sys.stdout.flush()


@pytest.hookimpl(trylast=True)
def pytest_runtest_logreport(report):
	"""Insert a blank line after the PASSED/FAILED status line."""
	if report.when == "call":
		sys.stdout.write("\n")
		sys.stdout.flush()


@pytest.fixture(scope="session", autouse=True)
def disable_requests_cache():
	"""Tests should never read from or write to the requests cache."""
	with requests_cache.disabled():
		yield


@pytest.fixture(scope="session", autouse=True)
def clear_downloads():
	"""Clear the downloads directory once before the entire test session."""
	if DOWNLOADS_DIR.exists():
		shutil.rmtree(DOWNLOADS_DIR)
	DOWNLOADS_DIR.mkdir(parents=True, exist_ok=True)