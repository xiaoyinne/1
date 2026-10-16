from pathlib import Path
import sys
import json
import numpy as np
sys.path.insert(0,'/home/yaw/fastlio_week2/scancontext/vendor/PyICP-SLAM-master')
from utils.ScanContextManager import ptcloud2sc,sc2rk,distance_sc
root=Path('/mnt/d/nclt_student3')
ref=np.load(root/'reference_audit/2012-01-08_scan_reference.npz',allow_pickle=False)
stamp=int(ref['stamps_us'][0])
p=root/'2012-01-08/velodyne_sync'/f'{stamp}.bin'
dtype=np.dtype([('x','<u2'),('y','<u2'),('z','<u2'),('intensity','u1'),('laser','u1')])
raw=np.fromfile(p,dtype=dtype)
xyz=np.column_stack([raw[k] for k in ['x','y','z']]).astype(float)*.005-100
xyz*=np.array([1,-1,-1])
r=np.linalg.norm(xyz[:,:2],axis=1)
xyz=xyz[(r>1)&(r<80)]
sc=ptcloud2sc(xyz.copy(),[20,60],80)
d,shift=distance_sc(sc,sc)
assert np.isfinite(sc).all() and sc.shape==(20,60)
assert np.isfinite(d) and abs(d)<1e-8
report={'date':'2012-01-08','stamp_us':stamp,'points_used':len(xyz),
        'descriptor_shape':list(sc.shape),'ring_key_shape':list(sc2rk(sc).shape),
        'active_sectors':int((np.linalg.norm(sc,axis=0)>0).sum()),
        'self_distance':float(d),'note':'Single-frame input compatibility check, not cross-date retrieval.'}
(root/'descriptor_input_check.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2),flush=True)
