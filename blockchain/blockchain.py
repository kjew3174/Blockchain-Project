from typing import Any
from blockchain.block import Block
import time


class Blockchain:
    def __init__(self) -> None:

        self.chain: list[Block] = []
        self.pending_transactions: list[dict[str, Any]] = []
        self.create_genesis_block()

    def create_genesis_block(self) -> None: # 최초 블록 생성

        genesis_block = Block(0, "0", time.time(), [])
        self.chain.append(genesis_block)

    def get_latest_block(self) -> Block: # 최신 블록 반환

        return self.chain[-1]

    def create_new_block(self) -> Block: # 새 블록 생성

        latest_block = self.get_latest_block()
        new_block = Block(
            index=latest_block.index + 1,
            previous_hash=latest_block.hash,
            timestamp=time.time(),
            transactions=self.pending_transactions
        )
        self.pending_transactions = []  # 새로운 블록에 포함된 트랜잭션은 초기화
        return new_block

    def add_block(self, block: Block) -> None: # 블록 추가

        self.chain.append(block)

    def replace_chain(
            self,
            new_chain: list[dict[str, Any]]
        ) -> None: # 새 체인으로 교체

        self.chain = [Block(**block_data) for block_data in new_chain]
