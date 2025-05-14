import unittest
from storage.erasure_code import ErasureCode

class TestErasureCode(unittest.TestCase):
    def setUp(self):
        self.ec = ErasureCode(k=4, n=6)
        self.data = b"Hello, this is a test message!"

    def test_encoding_decoding(self):
        encoded = self.ec.encode(self.data)
        decoded = self.ec.decode(encoded)
        self.assertEqual(decoded, self.data)

if __name__ == '__main__':
    unittest.main()
