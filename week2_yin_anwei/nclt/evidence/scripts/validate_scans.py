from pathlib import Path
import json
import numpy as np
import struct
import sys

root=Path('/mnt/d/nclt_student3')
dtype=np.dtype([('x','<u2'),('y','<u2'),('z','<u2'),('intensity','u1'),('laser','u1')])
assert dtype.itemsize==8
reports={}
dates=sys.argv[1:] or ['2012-01-08','2012-02-05']
for date in dates:
    extraction=json.loads((root/f'{date}_extraction.json').read_text())
    files=sorted((root/date/'velodyne_sync').glob('*.bin'))
    assert len(files)==extraction['scans']
    stamps=np.array([int(p.stem) for p in files],dtype=np.int64)
    assert np.all(np.diff(stamps)>0)
    ref=np.load(root/'reference_audit'/f'{date}_graph_reference.npz',allow_pickle=False)
    found=np.isin(ref['stamps_us'],stamps)
    selected=np.unique(np.linspace(0,len(files)-1,32,dtype=int))
    radii=[];zs=[];counts=[];lasers=set()
    for i in selected:
        raw=np.fromfile(files[i],dtype=dtype)
        with files[i].open('rb') as f:
            first=struct.unpack('<HHHBB',f.read(8))
        assert first==tuple(int(raw[k][0]) for k in dtype.names)
        xyz=np.column_stack([raw[k] for k in ['x','y','z']]).astype(np.float64)*0.005-100.
        assert len(xyz)>0 and np.isfinite(xyz).all()
        assert int(raw['laser'].max())<=31
        # Proper rotation from forward/right/down to forward/left/up.
        flu=xyz*np.array([1.,-1.,-1.])
        assert np.allclose(np.linalg.norm(flu,axis=1),np.linalg.norm(xyz,axis=1))
        radii.append(np.linalg.norm(flu[:,:2],axis=1))
        zs.append(flu[:,2]);counts.append(len(raw));lasers.update(raw['laser'].tolist())
    reports[date]={'scan_count':len(files),'span_s':float((stamps[-1]-stamps[0])/1e6),
        'scan_interval_median_s':float(np.median(np.diff(stamps))/1e6),
        'scan_interval_max_s':float(np.max(np.diff(stamps))/1e6),
        'usable_reference_nodes':len(found),'reference_nodes_with_exact_scan':int(found.sum()),
        'reference_nodes_missing_scan':ref['stamps_us'][~found].tolist(),
        'decoded_sample_scans':len(selected),'sample_point_count_min':min(counts),
        'sample_point_count_max':max(counts),'laser_ids':sorted(lasers),
        'sample_horizontal_radius_percentiles_m':np.percentile(np.concatenate(radii),[50,90,99]).tolist(),
        'sample_flu_height_percentiles_m':np.percentile(np.concatenate(zs),[1,50,99]).tolist(),
        'format':'Little endian uint16 x/y/z, uint8 intensity/laser. xyz=raw*0.005-100.',
        'frame':'Source: body FRD. Descriptor convention: body FLU, rotation diag(1,-1,-1). Do not apply lidar extrinsics again.'}
    print(json.dumps(reports[date],indent=2),flush=True)
    np.savez_compressed(root/'reference_audit'/f'{date}_scan_reference.npz',
        **{k:ref[k][found] for k in ref.files})
name='scan_validation.json' if len(dates)==2 else f'scan_validation_{dates[0]}.json'
(root/name).write_text(json.dumps(reports,indent=2),encoding='utf-8')
