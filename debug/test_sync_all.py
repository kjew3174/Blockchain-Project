import os
import sys
import unittest
import subprocess
import time
import requests

# 프로젝트 루트 및 네트워크 디렉터리 경로
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
NETWORK_DIR = os.path.join(PROJECT_ROOT)

# PYTHONPATH에 프로젝트 루트를 추가
sys.path.insert(0, PROJECT_ROOT)

class TestSyncAll(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 노드1 서브프로세스 실행 (포트 5000)
        env1 = {**os.environ, "FLASK_RUN_PORT": "5000"}
        # 노드2 서브프로세스 실행 (포트 5001)
        env2 = {**os.environ, "FLASK_RUN_PORT": "5001"}

        cls.proc1 = subprocess.Popen(
            ["python", "network/node.py"], cwd=NETWORK_DIR, env=env1
        )
        cls.proc2 = subprocess.Popen(
            ["python", "network/node.py"], cwd=NETWORK_DIR, env=env2
        )

        # 서버가 완전히 시작될 때까지 대기
        time.sleep(5)

    @classmethod
    def tearDownClass(cls):
        cls.proc1.terminate()
        cls.proc2.terminate()
        cls.proc1.wait()
        cls.proc2.wait()

    def test_sync_all(self):
        # 노드1과 노드2가 서로 발견되었는지 확인
        nodes1 = requests.get("http://localhost:5000/get_nodes").json().get("nodes", [])
        nodes2 = requests.get("http://localhost:5001/get_nodes").json().get("nodes", [])
        self.assertTrue(any("127.0.0.1" in ip for ip in nodes1))
        self.assertTrue(any("127.0.0.1" in ip for ip in nodes2))

        # 노드1에서 블록 채굴
        resp_mine = requests.get("http://localhost:5000/mine")
        self.assertEqual(resp_mine.status_code, 200)

        # 노드2에서 동기화 호출
        r = requests.get("http://localhost:5001/sync_all")
        self.assertEqual(r.status_code, 200)
        msg = r.json().get("message", "")
        self.assertIn("Synchronization complete", msg)

        # 동기화 후 체인 길이 비교
        chain1 = requests.get("http://localhost:5000/get_chain").json().get("chain", [])
        chain2 = requests.get("http://localhost:5001/get_chain").json().get("chain", [])
        self.assertEqual(len(chain1), len(chain2))

if __name__ == "__main__":
    unittest.main()
