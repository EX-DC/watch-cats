import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import watchcats  # noqa: E402
from check_version import versions  # noqa: E402


class VersionTests(unittest.TestCase):
    def test_semver_format(self):
        self.assertRegex(watchcats.__version__, r"^\d+\.\d+\.\d+$")

    def test_all_sources_agree(self):
        file_v, py_v, log_v = versions()
        self.assertEqual(file_v, py_v)
        self.assertEqual(py_v, log_v)


if __name__ == "__main__":
    unittest.main()
