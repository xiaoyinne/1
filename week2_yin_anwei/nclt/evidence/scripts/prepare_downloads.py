from pathlib import Path, PurePosixPath
import gzip
import tarfile
import hashlib
import json
import shutil
import time
import csv

SOURCE = Path('D:/chromeDownload')
ROOT = Path('D:/nclt_student3')
ROOT.mkdir(exist_ok=True)

class HashedReader:
    def __init__(self, f):
        self.f = f
        self.h = hashlib.sha256()
        self.n = 0
    def read(self, n=-1):
        b = self.f.read(n)
        self.h.update(b)
        self.n += len(b)
        return b

for date in ['2012-01-08', '2012-02-05']:
    archive = SOURCE / (date + '_vel.tar (1).gz')
    out = ROOT / date
    report_path = ROOT / (date + '_extraction.json')
    if report_path.exists():
        print('Already completed:', report_path, flush=True)
        continue
    out.mkdir(exist_ok=True)
    count = points = 0
    stamps = []
    entries = []
    started = last = time.monotonic()
    print('Starting', archive.name, flush=True)
    with archive.open('rb') as raw:
        reader = HashedReader(raw)
        with gzip.GzipFile(fileobj=reader) as gz:
            with tarfile.open(fileobj=gz, mode='r|', bufsize=1024*1024) as tar:
                for m in tar:
                    p = PurePosixPath(m.name)
                    if p.is_absolute() or '..' in p.parts:
                        raise RuntimeError('Unsafe member: ' + m.name)
                    selected = (m.isfile() and len(p.parts) == 3 and
                                p.parts[0] == date and p.parts[1] == 'velodyne_sync'
                                and p.suffix == '.bin' and p.stem.isdigit())
                    if selected:
                        if m.size <= 0 or m.size % 8:
                            raise RuntimeError('Invalid scan byte count: ' + m.name)
                        dst = out / 'velodyne_sync' / p.name
                        dst.parent.mkdir(exist_ok=True)
                        part = dst.with_suffix('.bin.partial')
                        h = hashlib.sha256()
                        n = 0
                        with tar.extractfile(m) as f, part.open('wb') as w:
                            while b := f.read(1024*1024):
                                w.write(b)
                                h.update(b)
                                n += len(b)
                        if n != m.size:
                            raise RuntimeError('Truncated member: ' + m.name)
                        part.replace(dst)
                        stamps.append(int(p.stem))
                        entries.append([p.name, n, h.hexdigest()])
                        points += n // 8
                        count += 1
                    if time.monotonic()-last > 20:
                        print(date, 'compressed read GiB', round(reader.n/2**30,2),
                              'scans', count, 'elapsed s', round(time.monotonic()-started), flush=True)
                        last=time.monotonic()
            # Consume the gzip trailer to enforce CRC and uncompressed length validation.
            while gz.read(4*1024*1024):
                pass
        if reader.n != archive.stat().st_size:
            raise RuntimeError('Archive not completely consumed')
        archive_hash = reader.h.hexdigest()
    if not count or len(set(stamps)) != len(stamps):
        raise RuntimeError('Missing scans or duplicate timestamps')
    with (out/'scan_manifest.csv').open('w', newline='', encoding='utf-8') as f:
        w=csv.writer(f);w.writerow(['file','bytes','sha256']);w.writerows(sorted(entries))
    reference = {}
    for prefix in ['groundtruth_', 'cov_']:
        src = SOURCE/(prefix+date+'.csv')
        dst = out/src.name
        shutil.copy2(src,dst)
        reference[dst.name]={'bytes':dst.stat().st_size,'sha256':hashlib.sha256(dst.read_bytes()).hexdigest()}
    report={'date':date,'archive':str(archive),'archive_bytes':archive.stat().st_size,
            'archive_sha256':archive_hash,'gzip_crc_validated':True,'scans':count,
            'total_points':points,'first_stamp_us':min(stamps),'last_stamp_us':max(stamps),
            'span_seconds':(max(stamps)-min(stamps))/1e6,'reference_files':reference,
            'elapsed_s':round(time.monotonic()-started,2),
            'note':'Only velodyne_sync scans extracted. Local hashes, not comparison with an official checksum.'}
    report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2),flush=True)
