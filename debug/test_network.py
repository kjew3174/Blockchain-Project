import unittest
import requests

class TestNetwork(unittest.TestCase):
    def setUp(self):
        self.node_url = "http://localhost:5000"

    def test_sync_nodes(self):
        try:
            response = requests.get(f"{self.node_url}/sync")
            self.assertEqual(response.status_code, 200)
            self.assertIn("message", response.json())
        except Exception as e:
            self.fail(f"Sync test failed: {e}")

if __name__ == '__main__':
    unittest.main()
