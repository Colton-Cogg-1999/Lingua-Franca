"""Run mutually exclusive geography treatments sequentially on the same workers."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
from .longrun import durable_json


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--plans',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--worker-url',action='append',default=[])
    parser.add_argument('--execution',choices=['kubernetes','local'],default='kubernetes')
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--brokers',default='redpanda:9092')
    args=parser.parse_args()
    args.output.mkdir(parents=True,exist_ok=True)
    names=['historical-main','historical-continuous','historical-related']
    for index,name in enumerate(names):
        durable_json(args.output/'suite-status.json',dict(state='running',active=name,index=index+1,total=len(names)))
        command=[sys.executable,'-m','galapagos.longrun','--plan',str(args.plans/(name+'.json')),'--output',str(args.output/name),'--execution',args.execution,'--workers',str(args.workers),'--brokers',args.brokers]
        for url in args.worker_url:command+=['--worker-url',url]
        subprocess.run(command,check=True)
    durable_json(args.output/'suite-status.json',dict(state='complete',runs=names))

if __name__=='__main__':main()
