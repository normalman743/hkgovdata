import subprocess
import sys

import pytest


@pytest.mark.parametrize("module", ["discover", "download"])
def test_module_help_outside_checkout(tmp_path, module):
    result = subprocess.run(
        [sys.executable, "-B", "-m", f"hkgovdata.{module}", "--help"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert f"python -m hkgovdata.{module}" in result.stdout


@pytest.mark.parametrize("section", ["parameters", "category", "provider", "format"])
def test_packaged_search_reference_outside_checkout(tmp_path, section):
    result = subprocess.run(
        [sys.executable, "-B", "-m", "hkgovdata.discover", "search-params", section],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("## ")
