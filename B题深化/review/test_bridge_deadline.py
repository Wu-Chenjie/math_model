"""Transport failure tests: local HTTP only, no formal simulator session."""
import json
import math
import sys
import threading
import time
import unittest
import subprocess
from pathlib import Path
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import bridge
from mocksim.client import ProtocolError

class FakeClient:
    def __init__(self, remaining=1200, rejected=False):
        self.remaining=remaining; self.rejected=rejected; self.actions=[]
    def enter(self): return {'accepted':True,'remaining_real_duration_s':self.remaining}
    def measure(self,*args):
        self.actions.append('measure')
        return {'accepted':not self.rejected,'virtual_time_s':0,'measure_result':'no_signal'}
    def exit(self):
        self.actions.append('exit')
        return {'accepted':True,'virtual_time_s':0}

class DeadlineTests(unittest.TestCase):
    def test_non_200_success_status_is_rejected(self):
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                self.rfile.read(int(self.headers['Content-Length']))
                data=json.dumps({'accepted':True,'virtual_time_s':0}).encode()
                self.send_response(201);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            c=bridge.DeadlineClient(base_url=f'http://127.0.0.1:{server.server_port}',robot_id='REVIEW')
            with self.assertRaises(ProtocolError):c.enter()
        finally:server.shutdown();server.server_close()
    def test_remaining_zero_starts_no_action(self):
        c=FakeClient(remaining=0)
        with self.assertRaises(TimeoutError): bridge.drive(3,c)
        self.assertEqual(c.actions,[])

    def test_rejected_action_never_counts_as_observation(self):
        c=FakeClient(rejected=True)
        with self.assertRaises(bridge.Rejected): bridge.drive(3,c)
        self.assertEqual(c.actions,['measure'])

    def test_solver_without_stdout_honors_short_deadline(self):
        c=FakeClient(remaining=.25)
        original=subprocess.Popen
        def silent(*args,**kwargs):
            return original([sys.executable,'-c','import time; time.sleep(2)'],**kwargs)
        start=time.perf_counter()
        with patch.object(bridge.subprocess,'Popen',side_effect=silent):
            with self.assertRaises(TimeoutError): bridge.drive(3,c)
        self.assertLess(time.perf_counter()-start,1.0)
        self.assertNotIn('measure',c.actions)

    def test_retry_reuses_identical_id_and_body(self):
        records=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                raw=self.rfile.read(int(self.headers['Content-Length']));records.append(raw)
                if len(records)==1:
                    self.close_connection=True; self.connection.close();return
                data=json.dumps({'accepted':True,'virtual_time_s':6,'measure_result':'no_signal'}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            def log_message(self,*args): pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            cls=getattr(bridge,'DeadlineClient',bridge.RobotClient)
            c=cls(base_url=f'http://127.0.0.1:{server.server_port}',robot_id='REVIEW',retry_backoff_s=.001)
            c.deadline_at=time.perf_counter()+1
            self.assertTrue(c.measure(0,0,1)['accepted'])
            self.assertEqual(len(records),2)
            self.assertEqual(records[0],records[1])
            self.assertEqual(c.counter,1)
        finally: server.shutdown();server.server_close()

    def test_expired_transport_deadline_sends_nothing(self):
        cls=getattr(bridge,'DeadlineClient',bridge.RobotClient)
        c=cls(base_url='http://127.0.0.1:1',robot_id='REVIEW',timeout_s=.01,retries=0)
        c.deadline_at=time.perf_counter()-1
        with self.assertRaises(TimeoutError):c.measure(0,0,1)
        self.assertEqual(c.stats.requests,0)

    def test_position_is_not_rounded_before_geometry_observation(self):
        c=bridge.DeadlineClient(robot_id='REVIEW')
        captures=[]
        c.post=lambda path,payload:captures.append((path,payload)) or {'accepted':True}
        x,y=0.,-.00000049
        c.measure(x,y,1);c.clear(x,y,1)
        for _,payload in captures:
            self.assertEqual(payload['position'],{'x':x,'y':y})
        eps=math.radians(1.005)
        z=(1000*math.cos(eps-1e-12),1000*math.sin(eps-1e-12))
        # If the old serializer moved the sensor to (0,0), a legal reading of
        # 0.00 degrees excludes this true source from the solver's retained cone.
        excess=-math.tan(eps)*z[0]+z[1]-y
        self.assertGreater(excess,1e-9)
        # Full float transport keeps physical and solver coordinates identical.
        self.assertEqual(captures[0][1]['position']['y'],y)

    def test_slow_http_body_cannot_extend_total_deadline(self):
        records=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                records.append(self.rfile.read(int(self.headers['Content-Length'])))
                data=json.dumps({'accepted':True,'virtual_time_s':6,'measure_result':'no_signal'}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(data)));self.end_headers()
                try:
                    for value in data:
                        self.wfile.write(bytes([value]));self.wfile.flush();time.sleep(.015)
                except OSError:pass
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            c=bridge.DeadlineClient(base_url=f'http://127.0.0.1:{server.server_port}',robot_id='REVIEW',retries=5)
            start=time.perf_counter();c.deadline_at=start+.15
            with self.assertRaises(TimeoutError):c.measure(0,0,1)
            self.assertLess(time.perf_counter()-start,.5)
            with self.assertRaises(TimeoutError):c.exit()
            self.assertEqual(len(records),1)
        finally:server.shutdown();server.server_close()

    def test_retry_backoff_is_limited_by_remaining_duration(self):
        records=[]
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                records.append(self.rfile.read(int(self.headers['Content-Length'])))
                self.close_connection=True;self.connection.close()
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            c=bridge.DeadlineClient(base_url=f'http://127.0.0.1:{server.server_port}',robot_id='REVIEW',retry_backoff_s=1)
            start=time.perf_counter();c.deadline_at=start+.1
            with self.assertRaises(TimeoutError):c.measure(0,0,1)
            self.assertLess(time.perf_counter()-start,.5)
            self.assertEqual(len(records),1)
        finally:server.shutdown();server.server_close()

if __name__=='__main__':unittest.main(verbosity=2)
