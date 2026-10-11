import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime_report import summarize


class RuntimeReportTest(unittest.TestCase):
    def test_counts_distinguish_input_processing_and_recording(self):
        manifest = {
            'playback_rate': .5, 'status': 'completed_needs_accuracy_evaluation',
            'bag_topic_counts': {'/hesai/pandar': 100, '/alphasense/imu': 4000},
            'trajectory_poses': 83,
            'node_diagnostics': {
                'lidar_qos_depth': 5, 'imu_qos_depth': 10,
                'lidar_received': 90, 'imu_received': 3500, 'synced_frames': 89,
                'pending_lidar': 1, 'first_scan_skipped': 1,
                'empty_undistorted_skipped': 2, 'map_initialization_skipped': 1,
                'too_few_downsampled_skipped': 1, 'odometry_published': 84
            }
        }
        report = summarize(manifest)
        self.assertEqual(report['lidar_not_observed_by_callback'], 10)
        self.assertEqual(report['imu_not_observed_by_callback'], 500)
        self.assertEqual(report['lidar_accounting_residual'], 0)
        self.assertEqual(report['processing_accounting_residual'], 0)
        self.assertEqual(report['odometry_not_observed_by_recorder'], 1)

    def test_missing_diagnostics_is_not_zero_loss(self):
        with self.assertRaisesRegex(ValueError, 'No node diagnostics'):
            summarize({})


if __name__ == '__main__':
    unittest.main()
