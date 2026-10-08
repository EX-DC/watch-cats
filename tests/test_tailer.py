import os
import tempfile
import unittest

import helpers  # noqa: F401
from watchcats.tailer import Tailer


class TailerTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.dir.name, "a.log")

    def tearDown(self):
        self.dir.cleanup()

    def write(self, text, mode="a"):
        with open(self.path, mode) as f:
            f.write(text)

    def test_missing_file(self):
        self.assertEqual(Tailer(self.path).read_new(), [])

    def test_reads_only_new_complete_lines(self):
        t = Tailer(self.path)
        self.write("one\ntwo\npart")
        self.assertEqual(t.read_new(), ["one", "two"])
        self.assertEqual(t.read_new(), [])
        self.write("ial\nthree\n")
        self.assertEqual(t.read_new(), ["partial", "three"])

    def test_resumes_from_saved_state(self):
        self.write("a\nb\n")
        t = Tailer(self.path)
        t.read_new()
        t2 = Tailer(self.path, t.inode, t.offset)
        self.write("c\n")
        self.assertEqual(t2.read_new(), ["c"])

    def test_rotation_and_truncate(self):
        t = Tailer(self.path)
        self.write("old1\nold2\n")
        t.read_new()
        os.rename(self.path, self.path + ".1")
        self.write("new1\n", "w")
        self.assertEqual(t.read_new(), ["new1"])
        self.write("x\n", "w")  # truncated, shorter than saved offset
        self.assertEqual(t.read_new(), ["x"])


if __name__ == "__main__":
    unittest.main()
