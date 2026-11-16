from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from galapagos.society import Ledger, initialize, interpret, rng_for, schedule, step

class SocietyTests(unittest.TestCase):
    def test_resource_balance_and_profitable_trade(self):
        state=initialize(476,4)
        traded=0
        for _ in range(120):
            events,summary=step(state,476,120,'adaptive')
            self.assertLess(abs(summary['balance_residual']),1e-7)
            self.assertTrue(all(v>=-1e-9 for a in state['agents'] for v in a['inventory']))
            for event in events:
                if event[11]:
                    traded+=1
                    self.assertGreater(event[13],0);self.assertGreater(event[14],0)
                    self.assertEqual(event[10],1)
                    self.assertLess(event[12],event[13])
        self.assertGreater(traded,0)

    def test_no_omniscient_interpretation(self):
        agent=initialize(1,2)['agents'][0]
        self.assertIsNone(interpret(agent,'unseen',list(range(6)),rng_for(1)))
        self.assertEqual(interpret(agent,'nara',list(range(6)),rng_for(1)),0)
        self.assertIsNone(interpret(agent,'nara',[1,2],rng_for(1)))

    def test_fragmentation_and_reconnection_boundaries(self):
        self.assertEqual(schedule(4800,24000)[0],'connected')
        self.assertEqual(schedule(4801,24000)[2][2],[])
        self.assertEqual(schedule(15600,24000)[2][5],[])
        self.assertEqual(schedule(15601,24000)[2][2],[1,3])
        self.assertEqual(schedule(23521,24000)[0],'dense_contact')
        state=initialize(5,4)
        for _ in range(200):
            events,_=step(state,5,200,'adaptive')
            links=schedule(state['round'],200)[2]
            for e in events:
                if e[2]!=e[3]:self.assertIn(e[3],links[e[2]])

    def test_restart_is_identical_and_transaction_rolls_back(self):
        original=initialize(476,3); split=deepcopy(original)
        for _ in range(40):step(original,476,40,'adaptive')
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'ledger.sqlite';ledger=Ledger(path,{'seed':476})
            for _ in range(17):
                events,summary=step(split,476,40,'adaptive');ledger.commit(split,events,summary)
            before=ledger.db.execute('SELECT count(*) FROM events').fetchone()[0]
            with self.assertRaises(sqlite3.IntegrityError):ledger.commit(split,events,summary)
            self.assertEqual(before,ledger.db.execute('SELECT count(*) FROM events').fetchone()[0])
            ledger.close();ledger=Ledger(path,{'seed':476});split=ledger.restore()
            for _ in range(23):
                events,summary=step(split,476,40,'adaptive');ledger.commit(split,events,summary)
            self.assertEqual(json.dumps(original,sort_keys=True),json.dumps(split,sort_keys=True));ledger.close()
            with self.assertRaisesRegex(ValueError,'mismatch'):Ledger(path,{'seed':999})

    def test_report_audit_detects_tampered_event(self):
        from galapagos.society_report import read_run
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory)
            config=dict(seed=476,rounds=20,population=3,condition='adaptive',source='test')
            ledger=Ledger(directory/'ledger.sqlite',config);state=initialize(476,3)
            for _ in range(20):
                events,summary=step(state,476,20,'adaptive');ledger.commit(state,events,summary)
            ledger.close()
            self.assertTrue(all(read_run(directory)['audit'].values()))
            with sqlite3.connect(directory/'ledger.sqlite') as db:
                db.execute('UPDATE events SET reward=reward+1 WHERE round=1 AND seq=0')
            self.assertFalse(read_run(directory)['audit']['summary_rewards'])

    def test_fixed_policy_does_not_update_values(self):
        state=initialize(476,4)
        for _ in range(10):step(state,476,100,'fixed')
        self.assertTrue(all(all(v==0 for q in a['q'].values() for v in q) for a in state['agents']))
        state=initialize(476,4);step(state,476,100,'adaptive')
        self.assertTrue(any(v!=0 for a in state['agents'] for q in a['q'].values() for v in q))

if __name__=='__main__':unittest.main()
