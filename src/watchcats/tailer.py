"""Incremental log reader: returns only new, complete lines; survives rotation."""
import os


class Tailer:
    def __init__(self, path, inode=None, offset=0, max_bytes=32 * 1024 * 1024):
        self.path, self.inode, self.offset, self.max_bytes = path, inode, offset, max_bytes

    def read_new(self):
        try:
            st = os.stat(self.path)
        except FileNotFoundError:
            return []
        if self.inode is not None and (st.st_ino != self.inode or st.st_size < self.offset):
            self.offset = 0  # rotated or truncated: start over
        self.inode = st.st_ino
        if st.st_size == self.offset:
            return []
        with open(self.path, "rb") as f:
            f.seek(self.offset)
            data = f.read(self.max_bytes)
        end = data.rfind(b"\n")
        if end < 0:  # only a partial line so far; wait for the rest
            return []
        self.offset += end + 1
        return data[:end].decode("utf-8", errors="replace").split("\n")
