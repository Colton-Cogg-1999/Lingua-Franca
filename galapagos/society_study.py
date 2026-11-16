"""Run a bounded, resumable study, report all outcomes, then optionally publish."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import time

from .society_report import generate


def command(args, **kwargs):
    return subprocess.run(args,check=True,text=True,**kwargs)


def publish(project,root,report):
    gh=shutil.which('gh')
    if not gh:raise RuntimeError('gh must be on PATH for publication')
    owner=command([gh,'api','user','--jq','.login'],capture_output=True).stdout.strip()
    if owner!='Colton-Cogg-1999':raise RuntimeError('GitHub account changed; refusing publication under another account')
    name=command(['git','config','user.name'],capture_output=True).stdout.strip()
    email=command(['git','config','user.email'],capture_output=True).stdout.strip()
    if name!='Colton Coggins' or email!='134796792+Colton-Cogg-1999@users.noreply.github.com':
        raise RuntimeError('Git author identity changed; refusing to attribute results to another author')
    # Stage only generated report files. Never stage runtime, credentials, or user edits.
    staged=command(['git','diff','--cached','--name-only'],capture_output=True).stdout.strip()
    if staged:raise RuntimeError('Existing staged changes require review before publication')
    paths=[str(p.relative_to(project)) for p in (report/'metrics.json',report/'report.md',report/'trajectories.png') if p.exists()]
    command(['git','add','--',*paths])
    if subprocess.run(['git','diff','--cached','--quiet']).returncode:
        command(['git','commit','-m','Report the completed Lingua Franca trade and learning study'])
    slug=f'{owner}/Lingua-Franca'
    remote=subprocess.run(['git','remote','get-url','origin'],capture_output=True,text=True)
    allowed={f'https://github.com/{slug}.git',f'git@github.com:{slug}.git',f'https://github.com/{slug}'}
    if remote.returncode==0 and remote.stdout.strip() not in allowed:
        raise RuntimeError('Origin points to another repository; refusing to change it')
    probe=subprocess.run([gh,'repo','view',slug,'--json','nameWithOwner,isPrivate'],capture_output=True,text=True)
    marker=root/'publication-created.json'
    if probe.returncode:
        command([gh,'repo','create',slug,'--public','--description','Artificial societies: trade, cultural change, reinforcement learning, and reproducible sociolinguistic experiments'])
        marker.write_text(json.dumps({'repository':slug,'created':time.time()}))
    elif not marker.exists() and remote.returncode:
        raise RuntimeError('Repository already exists and is not attached to this project; refusing to publish over it')
    if remote.returncode:
        command(['git','remote','add','origin',f'https://github.com/{slug}.git'])
    privacy=json.loads(command([gh,'repo','view',slug,'--json','isPrivate'],capture_output=True).stdout)
    if privacy['isPrivate']:raise RuntimeError('Expected a public repository; visibility requires review')
    command(['git','-c','credential.helper=','-c',f'credential.helper=!{shlex.quote(gh)} auth git-credential','push','-u','origin','main'])
    url=f'https://github.com/{slug}'
    (root/'publication.json').write_text(json.dumps({'url':url,'published':time.time()},indent=2))
    return url


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--rounds',type=int,default=24000)
    p.add_argument('--population',type=int,default=20);p.add_argument('--seeds',type=int,nargs='+',default=[476,911,2026]);p.add_argument('--publish',action='store_true')
    a=p.parse_args();root=a.output.resolve();root.mkdir(parents=True,exist_ok=True)
    project=Path(__file__).resolve().parents[1];os.chdir(project)
    specs=[dict(name=f'{condition}-{seed}',condition=condition,seed=seed) for seed in a.seeds for condition in ('adaptive','fixed','uniform')]
    manifest=dict(rounds=a.rounds,population=a.population,runs=specs,source=hashlib.sha256((project/"galapagos/society.py").read_bytes()).hexdigest())
    file=root/'manifest.json'
    if file.exists() and json.loads(file.read_text())!=manifest:raise RuntimeError('Study manifest mismatch')
    file.write_text(json.dumps(manifest,indent=2)+'\n')
    status=dict(state='running',completed=0,total=len(specs),started=time.time())
    def save():
        status['updated']=time.time();temp=root/'study.pending';temp.write_text(json.dumps(status,indent=2));temp.replace(root/'study.json')
    save()
    try:
        for index,spec in enumerate(specs):
            status.update(current=spec['name'],completed=index);save()
            with (root/f'{spec["name"]}.log').open('a') as log:
                command([sys.executable,'-m','galapagos.society','--output',str(root/spec['name']),'--rounds',str(a.rounds),'--population',str(a.population),'--seed',str(spec['seed']),'--condition',spec['condition']],stdout=log,stderr=subprocess.STDOUT)
            status['completed']=index+1;save()
        status['state']='auditing';save()
        report=project/'docs/results/lingua-franca' if a.publish else root/'report'
        passed=generate(root,report)
        status.update(state='reported',audit_passed=passed,report=str(report));save()
        # Negative or null scientific results are published. Integrity failures remain visible locally.
        if a.publish:
            if not passed:raise RuntimeError('Integrity audit failed; report written, publication held for correction')
            status['state']='publishing';save();status['url']=publish(project,root,report)
        status['state']='complete';save();print(json.dumps(status),flush=True)
    except BaseException as error:
        status.update(state='failed',error=f'{type(error).__name__}: {error}');save();raise

if __name__=='__main__':main()
