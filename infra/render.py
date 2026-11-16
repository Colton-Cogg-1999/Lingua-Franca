"""Render project-owned Kubernetes resources; does not deploy or delete resources."""
from copy import deepcopy
import json
from pathlib import Path
import yaml
from galapagos.policies import policy

NS = 'galapagos'
IMAGE = 'galapagos-regions:v2r2'
ROOT = Path(__file__).resolve().parents[1]
plan = json.loads((ROOT / 'examples/roman-fracture-2000.json').read_text())
smoke = deepcopy(plan)
smoke.update(name='region-smoke', rounds=9, diagnostic_interval=3)
smoke['config']['population'] = 6
for phase, end in zip(smoke['phases'], [3, 6, 9]):
    phase['through'] = end
metadata = lambda name: dict(name=name, namespace=NS)
items = [dict(apiVersion='v1', kind='Namespace', metadata={'name': NS})]
items += [dict(apiVersion='v1', kind='ServiceAccount', metadata=metadata('coordinator')),
          dict(apiVersion='rbac.authorization.k8s.io/v1', kind='Role', metadata=metadata('geography-controller'),
               rules=[dict(apiGroups=['networking.k8s.io'], resources=['networkpolicies'], verbs=['get','create','update'])]),
          dict(apiVersion='rbac.authorization.k8s.io/v1', kind='RoleBinding', metadata=metadata('geography-controller'),
               subjects=[dict(kind='ServiceAccount', name='coordinator', namespace=NS)],
               roleRef=dict(apiGroup='rbac.authorization.k8s.io', kind='Role', name='geography-controller')),
          dict(apiVersion='v1', kind='ConfigMap', metadata=metadata('experiment-plans'),
               data={'plan.json':json.dumps(plan), 'smoke.json':json.dumps(smoke)})]
items.append(dict(apiVersion='networking.k8s.io/v1', kind='NetworkPolicy', metadata=metadata('default-deny'),
                  spec=dict(podSelector={}, policyTypes=['Ingress','Egress'])))
dns = dict(namespaceSelector=dict(matchLabels={'kubernetes.io/metadata.name':'kube-system'}), podSelector=dict(matchLabels={'k8s-app':'kube-dns'}))
items.append(dict(apiVersion='networking.k8s.io/v1', kind='NetworkPolicy', metadata=metadata('coordinator-egress'),
    spec=dict(podSelector=dict(matchLabels={'app':'coordinator'}), policyTypes=['Egress'], egress=[
        {'to':[dict(podSelector=dict(matchLabels={'app':'region'}))], 'ports':[{'protocol':'TCP','port':8100}]},
        {'to':[dict(podSelector=dict(matchLabels={'app':'redpanda'}))], 'ports':[{'protocol':'TCP','port':9092}]},
        {'to':[dns], 'ports':[{'protocol':'TCP','port':53},{'protocol':'UDP','port':53}]},
        {'ports':[{'protocol':'TCP','port':443},{'protocol':'TCP','port':6443}]}])))
items.append(dict(apiVersion='networking.k8s.io/v1', kind='NetworkPolicy', metadata=metadata('ledger-access'),
    spec=dict(podSelector=dict(matchLabels={'app':'redpanda'}), policyTypes=['Ingress','Egress'],
              ingress=[{'from':[dict(podSelector=dict(matchLabels={'app':'coordinator'})),dict(podSelector=dict(matchLabels={'app':'redpanda'}))], 'ports':[{'protocol':'TCP','port':9092},{'protocol':'TCP','port':33145}]}],
              egress=[{'to':[dns], 'ports':[{'protocol':'TCP','port':53},{'protocol':'UDP','port':53}]},{'to':[dict(podSelector=dict(matchLabels={'app':'redpanda'}))],'ports':[{'protocol':'TCP','port':9092},{'protocol':'TCP','port':33145}]}])))
for island in range(6):
    labels={'app':'region','galapagos/island':str(island)}
    items.append(policy(island, list(range(6))))
    items.append(dict(apiVersion='v1', kind='Service', metadata=metadata(f'region-{island}'),
                      spec=dict(selector=labels, ports=[dict(port=8100,targetPort=8100)])))
    items.append(dict(apiVersion='apps/v1', kind='Deployment', metadata=metadata(f'region-{island}'),
        spec=dict(replicas=1, selector=dict(matchLabels=labels), template=dict(metadata=dict(labels=labels),
            spec=dict(automountServiceAccountToken=False, nodeSelector={'galapagos/island':str(island)}, containers=[
                dict(name='worker', image=IMAGE, imagePullPolicy='Never',
                     command=['python','-m','galapagos.regions','--island',str(island),'--host','0.0.0.0'],
                     resources=dict(requests={'cpu':'100m','memory':'96Mi'},limits={'cpu':'1','memory':'512Mi'}),
                     readinessProbe=dict(httpGet=dict(path='/health',port=8100),initialDelaySeconds=2),
                     livenessProbe=dict(httpGet=dict(path='/health',port=8100),initialDelaySeconds=10,timeoutSeconds=3))])))))
control={'node-role.kubernetes.io/control-plane':''}
tolerations=[dict(key='node-role.kubernetes.io/control-plane',operator='Exists',effect='NoSchedule')]
items.append(dict(apiVersion='v1',kind='Service',metadata=metadata('redpanda'),spec=dict(selector={'app':'redpanda'},ports=[dict(port=9092,targetPort=9092)])))
items.append(dict(apiVersion='apps/v1',kind='StatefulSet',metadata=metadata('redpanda'),spec=dict(serviceName='redpanda',replicas=1,
    selector=dict(matchLabels={'app':'redpanda'}),template=dict(metadata=dict(labels={'app':'redpanda'}),spec=dict(
        automountServiceAccountToken=False,nodeSelector=control,tolerations=tolerations,securityContext={'runAsUser':0},
        volumes=[dict(name='data',hostPath=dict(path='/galapagos-data/redpanda',type='DirectoryOrCreate'))],
        containers=[dict(name='redpanda',image='docker.redpanda.com/redpandadata/redpanda:v26.2.2',
            args=['redpanda','start','--mode','dev-container','--smp','1','--memory','1G','--reserve-memory','0M',
                  '--kafka-addr','0.0.0.0:9092','--advertise-kafka-addr','redpanda:9092',
                  '--rpc-addr','0.0.0.0:33145','--advertise-rpc-addr','redpanda:33145',
                  '--set','redpanda.internal_topic_replication_factor=1'],
            volumeMounts=[dict(name='data',mountPath='/var/lib/redpanda/data')],
            resources=dict(requests={'cpu':'500m','memory':'1536Mi'},limits={'cpu':'2','memory':'2Gi'}),
            readinessProbe=dict(httpGet=dict(path='/v1/status/ready',port=9644),initialDelaySeconds=10,periodSeconds=5),
            livenessProbe=dict(httpGet=dict(path='/v1/status/ready',port=9644),initialDelaySeconds=60,periodSeconds=10))])))))
(ROOT/'infra/regions.yaml').write_text(yaml.safe_dump_all(items,sort_keys=False))
for name,file,output in [('smoke','smoke.json','smoke'),('roman-fracture','plan.json','roman-fracture-2000')]:
    command=['python','-m','galapagos.longrun','--plan','/plans/'+file,'--output','/data/experiment/'+output]
    for i in range(6): command.extend(['--worker-url',f'http://region-{i}:8100'])
    job=dict(apiVersion='batch/v1',kind='Job',metadata=metadata(name),spec=dict(backoffLimit=6,parallelism=1,completions=1,
        template=dict(metadata=dict(labels={'app':'coordinator','experiment':name}),spec=dict(
            restartPolicy='OnFailure',serviceAccountName='coordinator',nodeSelector=control,tolerations=tolerations,
            volumes=[dict(name='data',hostPath=dict(path='/galapagos-data',type='Directory')),
                     dict(name='plans',configMap=dict(name='experiment-plans'))],containers=[dict(name='coordinator',
                image=IMAGE,imagePullPolicy='Never',command=command,
                resources=dict(requests={'cpu':'250m','memory':'256Mi'},limits={'cpu':'2','memory':'2Gi'}),
                volumeMounts=[dict(name='data',mountPath='/data'),dict(name='plans',mountPath='/plans',readOnly=True)])]))))
    (ROOT/f'infra/job-{name}.yaml').write_text(yaml.safe_dump(job,sort_keys=False))
