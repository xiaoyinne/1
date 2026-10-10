"""Convert ROS1 bag with rosbags 0.11.5, then normalize Humble QoS metadata."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import yaml


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--src', type=Path, required=True)
    parser.add_argument('--dst', type=Path, required=True)
    args = parser.parse_args()
    version = importlib.metadata.version('rosbags')
    if version != '0.11.5':
        parser.error(f'Expected rosbags 0.11.5; found {version}')
    if not args.src.is_file() or args.dst.exists():
        parser.error('Source must exist and destination must be new')
    command = [str(Path(sys.executable).parent / 'rosbags-convert'), '--src', str(args.src.resolve()), '--dst', str(args.dst.resolve())]
    subprocess.run(command, check=True)
    metadata = args.dst / 'metadata.yaml'
    shutil.copy2(metadata, args.dst / 'metadata.rosbags.yaml.bak')
    payload = yaml.safe_load(metadata.read_text())
    changed = 0
    for entry in payload['rosbag2_bagfile_information']['topics_with_message_count']:
        topic = entry['topic_metadata']
        qos = topic.get('offered_qos_profiles')
        if isinstance(qos, list):
            topic['offered_qos_profiles'] = yaml.safe_dump(qos) if qos else ''
            changed += 1
    metadata.write_text(yaml.safe_dump(payload, sort_keys=False), encoding='utf-8')
    manifest = {'rosbags_version': version, 'command': command,
                'source': str(args.src.resolve()), 'source_bytes': args.src.stat().st_size,
                'humble_qos_fields_normalized': changed,
                'metadata_sha256': hashlib.sha256(metadata.read_bytes()).hexdigest()}
    (args.dst / 'conversion_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Converted to {args.dst}; normalized {changed} QoS fields, original metadata backed up')


if __name__ == '__main__':
    main()
