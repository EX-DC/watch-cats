import shutil
import subprocess
import unittest

import helpers


@unittest.skipUnless(shutil.which("node"), "Node.js is not installed")
class FrontendTests(unittest.TestCase):
    def test_node_suite(self):
        r = subprocess.run(["node", "--test", str(helpers.ROOT / "tests" / "js" / "lib.test.js")], capture_output=True, text=True, timeout=120)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_scripts_parse(self):
        for f in ("lib.js", "app.js"):
            r = subprocess.run(["node", "--check", str(helpers.ROOT / "src/watchcats/web" / f)], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
