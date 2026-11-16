"""Render a separate ten-region cluster and sequential historical study jobs."""
from pathlib import Path
from copy import deepcopy
import json
import yaml
ROOT=Path(__file__).resolve().parents[1]
IMAGE='galapagos-regions:v3-history'
items=list(yaml.safe_load_all((ROOT/'infra/regions.yaml').read_text()))
plans={p.stem:json.loads(p.read_text()) for p in (ROOT/'examples').glob('historical-*.json')}
for item in items:
 if item['kind']=='ConfigMap':
  item['metadata']['name']='historical-plans';item['data']={name+'.json':json.dumps(plan) for name,plan in plans.items()}
 if item['kind']=='Deployment':item['spec']['template']['spec']['containers'][0]['image']=IMAGE
services=[x for x in items if x['kind']=='Service' and x['metadata']['name']=='region-0']
deploys=[x for x in items if x['kind']=='Deployment' and x['metadata']['name']=='region-0']
from galapagos.policies import policy
for i in range(6,10):
 service=deepcopy(services[0]);service['metadata']['name']=f'region-{i}';service['spec']['selector']['galapagos/island']=str(i);items.append(service)
 deploy=deepcopy(deploys[0]);deploy['metadata']['name']=f'region-{i}';spec=deploy['spec'];spec['selector']['matchLabels']['galapagos/island']=str(i);spec['template']['metadata']['labels']['galapagos/island']=str(i);spec['template']['spec']['nodeSelector']['galapagos/island']=str(i)
 command=spec['template']['spec']['containers'][0]['command'];command[command.index('--island')+1]=str(i);items.append(deploy)
 items.append(policy(i,[i]))
# Initial policy is closed; only the coordinator opens declared edges after launch.
items=[policy(int(x['metadata']['name'].split('-')[1]),[int(x['metadata']['name'].split('-')[1])]) if x['kind']=='NetworkPolicy' and x['metadata']['name'].startswith('region-') else x for x in items]
(ROOT/'infra/historical-resources.yaml').write_text(yaml.safe_dump_all(items,sort_keys=False))
for name in plans:
 job=yaml.safe_load((ROOT/'infra/job-roman-fracture.yaml').read_text());job['metadata']['name']=name;job['spec']['template']['metadata']['labels']['experiment']=name
 spec=job['spec']['template']['spec'];spec['restartPolicy']='Never'
 spec['volumes'][1]['configMap']['name']='historical-plans'
 c=spec['containers'][0];c['image']=IMAGE
 c['command']=['python','-m','galapagos.longrun','--plan',f'/plans/{name}.json','--output',f'/data/experiment/{name}']
 for i in range(10):c['command']+=['--worker-url',f'http://region-{i}:8100']
 (ROOT/f'infra/job-{name}.yaml').write_text(yaml.safe_dump(job,sort_keys=False))
cluster=yaml.safe_load((ROOT/'infra/kind-regions.yaml').read_text());cluster['name']='galapagos-history'
cluster['networking']['podSubnet']='10.246.0.0/16'
cluster['nodes'][0]['extraMounts'][0]['hostPath']=str(ROOT/'runtime/history-data')
cluster['nodes']+= [{'role':'worker','labels':{'galapagos/island':str(i)}} for i in range(6,10)]
(ROOT/'infra/kind-history.yaml').write_text(yaml.safe_dump(cluster,sort_keys=False))
calico=list(yaml.safe_load_all((ROOT/'infra/calico-rootless.yaml').read_text()))
for item in calico:
 if item['kind']=='DaemonSet':
  c=item['spec']['template']['spec']['containers'][0]
  c['env']=[x for x in c['env'] if x['name'] not in ('CALICO_IPV4POOL_CIDR','FELIX_VXLANVNI')]
  c['env'] += [{'name':'CALICO_IPV4POOL_CIDR','value':'10.246.0.0/16'},{'name':'FELIX_VXLANVNI','value':'4097'}]
(ROOT/'runtime/calico-history.yaml').write_text(yaml.safe_dump_all(calico,sort_keys=False))

job=yaml.safe_load((ROOT/'infra/job-historical-main.yaml').read_text())
job['metadata']['name']='historical-suite'
job['spec']['template']['metadata']['labels']['experiment']='historical-suite'
c=job['spec']['template']['spec']['containers'][0]
c['command']=['python','-m','galapagos.suite','--plans','/plans','--output','/data/experiment']
for i in range(10):c['command']+=['--worker-url',f'http://region-{i}:8100']
(ROOT/'infra/job-historical-suite.yaml').write_text(yaml.safe_dump(job,sort_keys=False))
