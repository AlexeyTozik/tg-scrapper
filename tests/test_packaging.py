import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import venv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class PackagingSmokeTests(unittest.TestCase):
    def test_build_wheel_and_console_help(self) -> None:
        with tempfile.TemporaryDirectory() as raw_dir:
            temp_dir = Path(raw_dir)
            dist_dir = temp_dir / "dist"
            venv_dir = temp_dir / "venv"

            try:
                subprocess.run(
                    [sys.executable, "-m", "build", "--sdist", "--wheel", "--outdir", str(dist_dir)],
                    cwd=REPO_ROOT,
                    check=True,
                )
            finally:
                shutil.rmtree(REPO_ROOT / "build", ignore_errors=True)
                shutil.rmtree(REPO_ROOT / "src" / "tg_scrapper.egg-info", ignore_errors=True)

            wheels = sorted(dist_dir.glob("tg_scrapper-*.whl"))
            self.assertEqual(len(wheels), 1)

            venv.EnvBuilder(with_pip=True).create(venv_dir)
            bin_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
            python_bin = bin_dir / ("python.exe" if os.name == "nt" else "python")
            cli_bin = bin_dir / ("tg-scrapper.exe" if os.name == "nt" else "tg-scrapper")

            subprocess.run([str(python_bin), "-m", "pip", "install", "--no-deps", str(wheels[0])], check=True)
            result = subprocess.run(
                [str(cli_bin), "--help"],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("Available commands:", result.stdout)
            self.assertIn("export", result.stdout)
            self.assertIn("query", result.stdout)


if __name__ == "__main__":
    unittest.main()
