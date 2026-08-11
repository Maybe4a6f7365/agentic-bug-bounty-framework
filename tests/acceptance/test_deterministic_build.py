from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "platform/your-lab-name/tools/build_bootstrap_tarball.sh"


def test_build_tool_versions_in_header():
    assert "REQUIRED_TOOL_VERSIONS" in SCRIPT.read_text()


def test_build_tar_sort_and_mtime_args():
    text = SCRIPT.read_text()
    assert "--sort=name" in text and "--mtime=@0" in text


def test_build_zstd_args_documented():
    assert "zstd -19 --no-progress" in SCRIPT.read_text()
