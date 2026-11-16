"""Kubernetes policy reconciliation plus actual per-region reachability probes."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import ssl
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from .regions import request


def policy(island, neighbors, namespace='galapagos'):
    peer = dict(podSelector=dict(matchExpressions=[dict(key='galapagos/island', operator='In', values=[str(i) for i in neighbors])]))
    coordinator = dict(podSelector=dict(matchLabels={'app': 'coordinator'}))
    dns = dict(namespaceSelector=dict(matchLabels={'kubernetes.io/metadata.name': 'kube-system'}), podSelector=dict(matchLabels={'k8s-app': 'kube-dns'}))
    return dict(apiVersion='networking.k8s.io/v1', kind='NetworkPolicy',
                metadata=dict(name=f'region-{island}', namespace=namespace),
                spec=dict(podSelector=dict(matchLabels={'galapagos/island': str(island)}),
                          policyTypes=['Ingress', 'Egress'],
                          ingress=[{'from': [coordinator, peer], 'ports': [{'protocol': 'TCP', 'port': 8100}]}],
                          egress=[{'to': [peer], 'ports': [{'protocol': 'TCP', 'port': 8100}]},
                                  {'to': [dns], 'ports': [{'protocol': 'UDP', 'port': 53}, {'protocol': 'TCP', 'port': 53}]}]))


class KubernetesPolicies:
    def __init__(self, namespace='galapagos'):
        self.namespace = namespace
        self.token_path = Path('/var/run/secrets/kubernetes.io/serviceaccount/token')
        self.context = ssl.create_default_context(cafile='/var/run/secrets/kubernetes.io/serviceaccount/ca.crt')
        self.base = 'https://' + os.environ['KUBERNETES_SERVICE_HOST'] + ':' + os.environ.get('KUBERNETES_SERVICE_PORT', '443')

    def call(self, path, method='GET', data=None):
        body = json.dumps(data).encode() if data is not None else None
        headers = {'Authorization': 'Bearer ' + self.token_path.read_text().strip(), 'Content-Type': 'application/json'}
        with urlopen(Request(self.base + path, body, headers, method=method), context=self.context, timeout=30) as reply:
            return json.load(reply)

    def apply(self, topology):
        base = f'/apis/networking.k8s.io/v1/namespaces/{self.namespace}/networkpolicies'
        for island, neighbors in enumerate(topology):
            desired = policy(island, neighbors, self.namespace)
            path = base + '/' + desired['metadata']['name']
            try:
                current = self.call(path)
                desired['metadata']['resourceVersion'] = current['metadata']['resourceVersion']
                self.call(path, 'PUT', desired)
            except HTTPError as error:
                if error.code != 404:
                    raise
                error.close()
                self.call(base, 'POST', desired)


def verify(topology, urls, timeout=90):
    deadline = time.monotonic() + timeout
    expected = [[j in neighbors for j in range(len(urls))] for neighbors in topology]
    def probe(url):
        return request(url + '/probe', {'urls': urls}, timeout=8)['reachable']
    while True:
        with ThreadPoolExecutor(max_workers=len(urls)) as executor:
            actual = list(executor.map(probe, urls))
        if actual == expected:
            return dict(expected=expected, observed=actual)
        if time.monotonic() >= deadline:
            raise RuntimeError(f'network policy not enforced: expected={expected}, observed={actual}')
        time.sleep(2)
