"""Small failure-path and format-contract checks; run via unittest discovery."""
import sys
from pathlib import Path
import subprocess
import tempfile
import unittest
import numpy as np

TOOLS = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TOOLS))
from common import load_tum, read_pcd


class ArtifactsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def tum(self, timestamps=(1, 2)):
        path = self.root / 'input.tum'
        # 90-degree rotation about Z, followed by identity.
        rows = [[timestamps[0], 1, 2, 3, 0, 0, 2**-.5, 2**-.5],
                [timestamps[1], 4, 5, 6, 0, 0, 0, 1]]
        np.savetxt(path, rows, fmt='%.12f')
        return path

    def test_export_rotation_translation_and_no_overwrite(self):
        command = [sys.executable, str(TOOLS / 'export_trajectory.py'), '--tum', str(self.tum()), '--output-dir', str(self.root)]
        subprocess.run(command, check=True, capture_output=True)
        values = np.loadtxt(self.root / 'trajectory_kitti.txt').reshape(-1, 3, 4)
        expected = [[0, -1, 0, 1], [1, 0, 0, 2], [0, 0, 1, 3]]
        np.testing.assert_allclose(values[0], expected, atol=1e-9)
        before = (self.root / 'trajectory_kitti.txt').read_bytes()
        self.assertNotEqual(subprocess.run(command, capture_output=True).returncode, 0)
        self.assertEqual((self.root / 'trajectory_kitti.txt').read_bytes(), before)

    def test_duplicate_timestamp_rejected(self):
        with self.assertRaisesRegex(ValueError, 'strictly increasing'):
            load_tum(self.tum((1, 1)))

    def test_non_unit_quaternion_rejected(self):
        path = self.tum()
        values = np.loadtxt(path)
        values[0, 4:8] = 0
        np.savetxt(path, values)
        with self.assertRaisesRegex(ValueError, 'quaternion'):
            load_tum(path)

    def test_pcd_payload_check_and_field_order(self):
        path = self.root / 'sample.pcd'
        header = b'VERSION .7\nFIELDS intensity z x y\nSIZE 4 4 4 4\nTYPE F F F F\nCOUNT 1 1 1 1\nWIDTH 2\nHEIGHT 1\nPOINTS 2\nDATA binary\n'
        payload = np.asarray([[10, 3, 1, 2], [20, 6, 4, 5]], dtype='<f4').tobytes()
        path.write_bytes(header + payload)
        _, xyz = read_pcd(path)
        np.testing.assert_array_equal(xyz, [[1, 2, 3], [4, 5, 6]])
        path.write_bytes(header + payload[:-4])
        with self.assertRaisesRegex(ValueError, 'payload length'):
            read_pcd(path)


if __name__ == '__main__':
    unittest.main()
