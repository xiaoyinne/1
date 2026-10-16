from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
root=Path('/mnt/d/nclt_student3/reference_audit')
fig,ax=plt.subplots(figsize=(10,6))
for date,color,label in [('2012-01-08','#167ca5','Database: 2012-01-08'),
                         ('2012-02-05','#d46c34','Query: 2012-02-05')]:
    a=np.load(root/f'{date}_graph_reference.npz',allow_pickle=False)
    p=a['poses_xyz_rpy']
    ax.scatter(p[:,1],p[:,0],s=5,c=color,label=label,alpha=.65)
ax.set(xlabel='East (m)',ylabel='North (m)',title='NCLT cross-date reference positions')
ax.set_aspect('equal');ax.grid(alpha=.2);ax.legend(loc='best')
fig.text(.5,.025,'Reference coverage diagnostic only; not retrieval results.',ha='center',fontsize=10)
fig.tight_layout(rect=(0,.04,1,1))
fig.savefig(root/'cross_date_reference.png',dpi=150,bbox_inches='tight')
print(root/'cross_date_reference.png')
