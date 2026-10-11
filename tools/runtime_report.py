"""Summarize source, callback and processing counts without equating them to accuracy."""
import argparse
import json
from pathlib import Path


def summarize(manifest):
    diagnostics = manifest.get('node_diagnostics')
    if diagnostics is None:
        raise ValueError('No node diagnostics: apply the runtime patch and rerun')
    source = manifest['bag_topic_counts']
    skipped = sum(diagnostics[key] for key in (
        'first_scan_skipped', 'empty_undistorted_skipped',
        'map_initialization_skipped', 'too_few_downsampled_skipped'))
    return {
        'playback_rate': manifest['playback_rate'],
        'lidar_qos_depth': diagnostics['lidar_qos_depth'],
        'imu_qos_depth': diagnostics['imu_qos_depth'],
        'source_lidar': source['/hesai/pandar'],
        'source_imu': source['/alphasense/imu'],
        'lidar_not_observed_by_callback': source['/hesai/pandar'] - diagnostics['lidar_received'],
        'imu_not_observed_by_callback': source['/alphasense/imu'] - diagnostics['imu_received'],
        'lidar_accounting_residual': diagnostics['lidar_received'] - diagnostics['synced_frames'] - diagnostics['pending_lidar'],
        'processing_accounting_residual': diagnostics['synced_frames'] - skipped - diagnostics['odometry_published'],
        'odometry_not_observed_by_recorder': diagnostics['odometry_published'] - manifest['trajectory_poses'],
        'diagnostics': diagnostics,
        'sampled_process_resources': manifest.get('sampled_process_resources', {}),
        'collection_status': manifest['status'],
        'notes': [
            'Source minus callback is unobserved input, not proof of the DDS loss mechanism.',
            'Accounting assumes this Hilti single-play run, no loop/reset, and one publisher per input.',
            'Queued samples not delivered before shutdown are also unobserved; pending_lidar covers only the application buffer.',
            'Frame time covers the synchronized timer processing, not preprocessing in the input callback.',
            'CPU/RSS are sampled from each spawned PID, not its descendants; CPU percent is relative to one CPU.',
            'Counts and clean exit do not establish geometric accuracy; inspect the separate evo evaluation.'
        ]
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output exists; choose a new path')
    report = summarize(json.loads(args.manifest.read_text()))
    args.output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({key: value for key, value in report.items()
                      if key not in ('diagnostics', 'sampled_process_resources', 'notes')}, indent=2))


if __name__ == '__main__':
    main()
