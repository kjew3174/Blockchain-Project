import os, sys, time
import unittest
import subprocess
import requests

# 프로젝트 루트를 PYTHONPATH에 추가
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

class TestSyncAll(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 두 개의 노드를 각각 포트 5000, 5001에서 실행
        env1 = {**os.environ, "PORT": "5000"}
        env2 = {**os.environ, "PORT": "5001"}
        # node.py 경로
        node_script = os.path.join(PROJECT_ROOT, "network", "node.py")

        cls.proc1 = subprocess.Popen(
            [sys.executable, node_script],
            env=env1
        )
        cls.proc2 = subprocess.Popen(
            [sys.executable, node_script],
            env=env2
        )
        # 서버가 완전히 기동될 때까지 대기
        time.sleep(5)

    @classmethod
    def tearDownClass(cls):
        cls.proc1.terminate()
        cls.proc2.terminate()
        cls.proc1.wait()
        cls.proc2.wait()

    def test_sync_all(self):
        # 1) /get_nodes 확인
        for port in (5000, 5001):
            url = f"http://localhost:{port}/get_nodes"
            resp = requests.get(url)
            self.assertEqual(resp.status_code, 200, f"GET {url} returned {resp.status_code}")
            try:
                nodes = resp.json().get("nodes", [])
            except Exception as e:
                self.fail(f"Invalid JSON from {url}: {e}")
            self.assertIsInstance(nodes, list)
        
        # 2) node1에서 블록 채굴 전, 트랜잭션 추가
        tx = {"sender": "Alice", "receiver": "Bob", "amount": 1.23}
        resp_tx = requests.post("http://localhost:5000/add_transaction", json=tx)
        self.assertEqual(resp_tx.status_code, 201, f"/add_transaction returned {resp_tx.status_code}")
        
        # 3) node1에서 블록 채굴
        resp_mine = requests.get("http://localhost:5000/mine")
        self.assertEqual(resp_mine.status_code, 200, f"/mine returned {resp_mine.status_code}")

        # 4) node2에서 동기화 호출
        resp_sync = requests.get("http://localhost:5001/sync_all")
        self.assertEqual(resp_sync.status_code, 200, f"/sync_all returned {resp_sync.status_code}")
        try:
            msg = resp_sync.json().get("message", "")
        except Exception as e:
            self.fail(f"Invalid JSON from /sync_all: {e}")
        self.assertIn("Synchronization complete", msg)

        # 5) 체인 길이 비교
        chain1 = requests.get("http://localhost:5000/get_chain").json().get("chain", [])
        chain2 = requests.get("http://localhost:5001/get_chain").json().get("chain", [])
        self.assertEqual(len(chain1), len(chain2), "Chain lengths do not match after sync")

if __name__ == "__main__":
    unittest.main()
