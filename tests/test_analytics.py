import json
import tempfile
from pathlib import Path
import unittest
from galapagos.analytics import Projection


class AnalyticsTests(unittest.TestCase):
    def test_duplicate_replay_and_boundary_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Projection(Path(directory)/'projection.sqlite')
            def record(offset,kind,**fields):
                event=dict(event_id=f'r:{offset}',run_id='r',round=1,kind=kind,**fields)
                return ('topic',0,offset,json.dumps(event).encode())
            records=[record(0,'initialized',plan={'name':'test'}),
                     record(1,'geography_changed',topology=[[0],[1]],checks={'expected':[[True,False],[False,True]],'observed':[[True,False],[False,True]]}),
                     record(2,'conversation',source_island=0,island=0,first_success=True,final_success=True),
                     record(3,'migration',source=0,destination=1),
                     record(4,'round_completed',summary={'round':1})]
            p.ingest(records)
            p.ingest(records)
            status=p.status()['runs'][0]
            self.assertEqual(status['conversations'],1)
            self.assertEqual(status['migrations'],1)
            self.assertEqual(status['boundary_violations'],1)
            self.assertEqual(status['unverifiable'],0)
            self.assertEqual(p.db.execute('SELECT offset_id FROM offsets').fetchone()[0],4)
            p.db.close()

    def test_conflicting_event_rolls_back_batch_and_offset(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Projection(Path(directory)/'projection.sqlite')
            event={'event_id':'same','run_id':'r','round':0,'kind':'initialized','plan':{'name':'one'}}
            p.ingest([('t',0,0,json.dumps(event).encode())])
            event['plan']['name']='two'
            with self.assertRaises(ValueError):
                p.ingest([('t',0,1,json.dumps(event).encode())])
            self.assertEqual(p.db.execute('SELECT offset_id FROM offsets').fetchone()[0],0)
            self.assertEqual(p.status()['runs'][0]['name'],'one')
            p.db.close()
