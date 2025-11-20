import time
import json
from blockchain.block import Block
from storage.erasure_code import ErasureCode
from storage.storage import Storage
import socket

class Blockchain:
    def __init__(self, k: int = 2, n: int = 3) -> None:
        """
        블록체인 생성자. 소거 코드 및 저장소 초기화
        :param k: 데이터 청크 수
        :param n: 총 청크 수 (데이터+패리티)
        """
        self.chain: list[Block] = []
        self.pending_transactions: list[dict] = []
        self.er: ErasureCode = ErasureCode(k, n)
        self.storage: Storage = Storage()
        self.node_id: str = self.get_node_id()
        self.create_genesis_block()

    def get_node_id(self) -> str:
        """현재 노드 식별자(ID)로 IP 주소 사용"""
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip

    def create_genesis_block(self) -> None:
        genesis = Block(0, "0", time.time(), [])
        self.store_block(genesis)
        self.chain.append(genesis)

    def get_latest_block(self) -> Block:
        return self.chain[-1]

    def create_new_block(self) -> Block:
        latest = self.get_latest_block()
        new_block = Block(
            index=latest.index + 1,
            previous_hash=latest.hash,
            timestamp=time.time(),
            transactions=self.pending_transactions
        )
        self.pending_transactions = []
        return new_block

    def add_block(self, block: Block) -> None:
        """
        블록 채굴 후 소거 코드를 적용하여 저장
        """
        self.chain.append(block)
        self.store_block(block)

    def store_block(self, block: Block, k: int | None = None, n: int | None = None) -> list[bytes]:
        """
        블록을 JSON으로 직렬화한 뒤 소거 코드로 인코딩하여 n개의 청크로 분할
        :return: n개의 청크 리스트
        """
        data_bytes = json.dumps(block.to_dict()).encode()
        chunks = self.er.encode(data_bytes, k, n)
        return chunks

    def replace_chain(self, new_chain: list[dict]) -> None:
        """
        체인을 교체합니다. (청크 저장은 node.py에서 처리)
        """
        self.chain = []
        for block_data in new_chain:
            block = Block(
                index=block_data['index'],
                previous_hash=block_data['previous_hash'],
                timestamp=block_data['timestamp'],
                transactions=block_data['transactions'],
                nonce=block_data.get('nonce', 0)
            )
            block.hash = block_data['hash']
            self.chain.append(block)

    def is_chain_valid(self) -> bool:
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            prev = self.chain[i-1]
            if current.hash != current.calculate_hash():
                return False
            if current.previous_hash != prev.hash:
                return False
        return True
