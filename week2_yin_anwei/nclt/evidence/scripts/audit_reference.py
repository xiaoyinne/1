from pathlib import Path
import json
import numpy as np
from scipy.spatial import cKDTree

source=Path('/mnt/d/chromeDownload')
out=Path('/mnt/d/nclt_student3/reference_audit')
out.mkdir(parents=True,exist_ok=True)
reports={}
positions={}
for date in ['2012-01-08','2012-02-05']:
    gt=np.loadtxt(source/f'groundtruth_{date}.csv',delimiter=',')
    cov=np.loadtxt(source/f'cov_{date}.csv',delimiter=',')
    assert gt.shape[1]==7 and cov.shape[1]==22
    assert np.isfinite(gt[:,0]).all() and np.isfinite(cov).all()
    t=gt[:,0].astype(np.int64)
    tc=cov[:,0].astype(np.int64)
    assert np.all(np.diff(t)>0) and np.all(np.diff(tc)>0)
    finite=np.isfinite(gt).all(axis=1)
    # Match to the original nearest GT record; never bridge invalid stretches.
    idx=np.searchsorted(t,tc).clip(0,len(t)-1)
    prev=np.maximum(idx-1,0)
    idx=np.where(np.abs(t[prev]-tc)<np.abs(t[idx]-tc),prev,idx)
    gap=np.abs(t[idx]-tc)
    keep=(tc>=t[0])&(tc<=t[-1])&finite[idx]&(gap<=20000)
    positions[date]=gt[idx[keep],1:4]
    np.savez_compressed(out/f'{date}_graph_reference.npz',
                        stamps_us=tc[keep],poses_xyz_rpy=gt[idx[keep],1:],
                        nearest_gt_gap_us=gap[keep],covariance_upper=cov[keep,1:])
    report={'date':date,'gt_rows':len(gt),'nonfinite_pose_rows':int((~finite).sum()),
            'gt_span_s':float((t[-1]-t[0])/1e6),'graph_nodes':len(tc),
            'usable_graph_nodes':int(keep.sum()),'excluded_graph_nodes':int((~keep).sum()),
            'max_nearest_gt_gap_ms':float(gap[keep].max()/1000),
            'xyz_min':positions[date].min(axis=0).tolist(),
            'xyz_max':positions[date].max(axis=0).tolist()}
    reports[date]=report
    print(json.dumps(report,indent=2),flush=True)

dist,_=cKDTree(positions['2012-01-08']).query(positions['2012-02-05'])
reports['cross_date_reference_diagnostic']={
    'query_graph_nodes':len(dist),'nearest_database_distance_m_percentiles':
    {str(p):float(np.percentile(dist,p)) for p in [0,25,50,75,95,100]},
    'within_5m':int((dist<=5).sum()),'within_10m':int((dist<=10).sum()),
    'note':'Reference location coverage only. No point-cloud overlap, retrieval, or localization success is established.'}
reports['reference_method']='Nearest original GT to covariance node timestamps, <=20 ms, no extrapolation or bridging invalid poses. Body coordinates: x forward, y right, z down. GT world is NED. Synchronized scans already use the body frame.'
(out/'report.json').write_text(json.dumps(reports,indent=2),encoding='utf-8')
print(json.dumps(reports['cross_date_reference_diagnostic'],indent=2),flush=True)
