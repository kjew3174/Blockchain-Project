import time
import json
from block import Block
from storage.erasure_code import ErasureCode
from storage.storage import Storage
import socket

class Blockchain:
    def __init__(self, k: int = 4, n: int = 6) -> None:
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

    def store_block(self, block: Block) -> None:
        """
        블록을 JSON으로 직렬화한 뒤 소거 코드로 인코딩하여 저장소에 분산 저장
        """
        data_bytes = json.dumps(block.to_dict()).encode()
        encoded = self.er.encode(data_bytes)
        # 소거 코드 결과를 단일 바이트 배열로 저장하거나, 필요시 조각별 저장
        # 여기서는 전체 인코딩된 데이터를 하나의 청크로 저장
        self.storage.save_chunk(encoded, self.node_id, block.index)

    def replace_chain(self, new_chain: list[dict]) -> None:
        """
        체인을 교체하고, 저장된 블록 데이터도 갱신 필요
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
            self.store_block(block)

    def is_chain_valid(self) -> bool:
        for i in range(1, len(self.chain)):
            current = self.chain[i]
            prev = self.chain[i-1]
            if current.hash != current.calculate_hash():
                return False
            if current.previous_hash != prev.hash:
                return False
        return True
