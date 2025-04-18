import unittest
from blockchain.block import Block
from blockchain.blockchain import Blockchain

class TestBlockchain(unittest.TestCase):
    def setUp(self):
        self.blockchain = Blockchain()

    def test_add_block(self):
        new_block = self.blockchain.create_new_block()
        self.blockchain.add_block(new_block)
        self.assertEqual(len(self.blockchain.chain), 2)

    def test_chain_validity(self):
        new_block = self.blockchain.create_new_block()
        self.blockchain.add_block(new_block)
        self.assertTrue(self.blockchain.is_valid_chain())

if __name__ == '__main__':
    unittest.main()
