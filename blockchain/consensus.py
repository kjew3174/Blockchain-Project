def proof_of_work(block, difficulty):
        target = "0" * difficulty
        while block.hash[:difficulty] != target:
            block.nonce += 1
            block.hash = block.calculate_hash()
        return block