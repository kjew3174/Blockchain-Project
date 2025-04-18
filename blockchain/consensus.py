def proof_of_work(block, difficulty):
        target = "0" * difficulty
        while block.hash[:difficulty] != target:
            block.nonce += 1
            block.hash = block.calculate_hash()
        return block
class Consensus:
    def proof_of_stake(self, blockchain):
          return True

    def validate_proof(self, block: Block, previous_block: Block) -> bool:
        if block.previous_hash != previous_block.hash:
            return False
        if block.hash != block.calculate_hash():
            return False
        return True