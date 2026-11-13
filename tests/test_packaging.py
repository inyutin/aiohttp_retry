import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path


def test_distributions_include_test_support_only_in_sdist(tmp_path: Path) -> None:
    source = Path(__file__).resolve().parents[1]
    project = tmp_path / "project"
    shutil.copytree(
        source,
        project,
        ignore=shutil.ignore_patterns(".git", ".venv", "build", "dist", "*.egg-info", "__pycache__", ".*cache"),
    )
    subprocess.run(  # noqa: S603
        [sys.executable, "setup.py", "sdist", "bdist_wheel"],
        cwd=project,
        check=True,
        capture_output=True,
        text=True,
    )

    expected_tests = {path.relative_to(project).as_posix() for path in (project / "tests").rglob("*.py")}
    with tarfile.open(next((project / "dist").glob("*.tar.gz"))) as archive:
        members = {name.split("/", 1)[1] for name in archive.getnames() if "/" in name}
    assert expected_tests <= members
    assert "aiohttp_retry/py.typed" in members

    with zipfile.ZipFile(next((project / "dist").glob("*.whl"))) as wheel:
        assert not any(name.startswith("tests/") for name in wheel.namelist())
        assert "aiohttp_retry/py.typed" in wheel.namelist()
