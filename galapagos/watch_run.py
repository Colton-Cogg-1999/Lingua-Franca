"""Refresh static run reports and finish with an independent ledger/count audit."""
import argparse
import json
from pathlib import Path
import sqlite3
import subprocess
import sys
import time


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('run',type=Path)
    parser.add_argument('--analytics',type=Path,required=True)
    parser.add_argument('--report-every',type=int,default=100)
    args=parser.parse_args()
    if args.report_every < 1:parser.error('report interval must be positive')
    rendered=-1
    while True:
        status_path=args.run/'status.json'
        if not status_path.exists():
            time.sleep(20)
            continue
        status=json.loads(status_path.read_text())
        round_number=status['round']
        if rendered<0 or round_number-rendered>=args.report_every or (status['state']=='complete' and rendered!=round_number):
            subprocess.run([sys.executable,'-m','galapagos.region_report',str(args.run)],check=True)
            rendered=round_number
            print(json.dumps({'report_round':round_number,'state':status['state']}),flush=True)
        if status['state']=='complete' and args.analytics.exists():
            with sqlite3.connect(f'file:{args.analytics.resolve()}?mode=ro',uri=True) as database:
                last=database.execute('SELECT max(round_id) FROM summaries WHERE run_id=?',(status['run_id'],)).fetchone()[0]
                if last==round_number:
                    observed=dict(database.execute('SELECT round_id,conversations FROM counts WHERE run_id=?',(status['run_id'],)))
                    violations=database.execute('SELECT sum(boundary_violations),sum(unverifiable) FROM counts WHERE run_id=?',(status['run_id'],)).fetchone()
                    expected={}
                    for folder in sorted((args.run/'rounds').glob('[0-9]*')):
                        summary=json.loads((folder/'summary.json').read_text())
                        if summary['round']:
                            expected[summary['round']]=summary['overall']['count']
                    published=json.loads((args.run/'published.json').read_text())['round']
                    audit=dict(run_id=status['run_id'],rounds=round_number,broker_published_through=published,
                               consumer_projected_through=last,expected_conversations=sum(expected.values()),
                               observed_conversations=sum(observed.values()),per_round_counts_match=observed==expected,
                               boundary_violations=violations[0] or 0,unverifiable=violations[1] or 0)
                    audit['passed']=(published==round_number and observed==expected and not any(violations))
                    (args.run/'completion-audit.json').write_text(json.dumps(audit,indent=2))
                    print(json.dumps(audit),flush=True)
                    if not audit['passed']:
                        raise RuntimeError('completed run failed independent ledger audit')
                    return
        time.sleep(20)


if __name__=='__main__':
    main()
