import time
import hashlib
from typing import Any


class Block:
    def __init__(self,
            index: int, # 해당 인덱스
            previous_hash: str, # 이전 블록 해시
            timestamp: float, # 생성 시간
            transactions: list[dict], # 트랜잭션 목록
            nonce: int = 0 # 작업 증명 난스값
        ) -> None:
        
        self.index = index
        self.previous_hash = previous_hash
        self.timestamp = timestamp
        self.transactions = transactions
        self.nonce = nonce
        self.hash = self.calculate_hash()

    def calculate_hash(self) -> str: # 해시값 계산

        block_string: str = f"{self.index}{self.previous_hash}{self.timestamp}{self.transactions}{self.nonce}"
        return hashlib.sha256(block_string.encode()).hexdigest()

    def to_dict(self) -> dict[str, Any]: # 딕셔너리로 변환
        
        return {
            "index": self.index,
            "previous_hash": self.previous_hash,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "nonce": self.nonce,
            "hash": self.hash
        }
