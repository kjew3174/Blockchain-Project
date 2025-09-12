import time
import hashlib
from typing import Any
import requests
import os
import json
import threading
import socket, requests
from flask import Flask, request, jsonify, Response
from reedsolo import RSCodec


NODE_LIST = [
    {"host": "106.101.3.108", "port": 5000}, # 이재윤 노트북
    {"host": "180.81.35.82", "port": 5001}, # 박주혁
    {"host": "180.81.35.82", "port": 5002} # 박건률
]
BLOCK_SIZE = 1024  # 블록 크기 설정
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
def proof_of_work(block: Block, difficulty):
        target = "0" * difficulty
        while block.hash[:difficulty] != target:
            block.nonce += 1
            block.hash = block.calculate_hash()
        return block
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

class Consensus:
    def proof_of_stake(self, blockchain: Any):
        return True

    def validate_proof(self, block: Block, previous_block: Block) -> bool:
        if block.previous_hash != previous_block.hash:
            return False
        if block.hash != block.calculate_hash():
            return False
        return True
    
class Transaction:
    def __init__(self, sender, receiver, amount):
        self.sender = sender
        self.receiver = receiver
        self.amount = amount
        self.timestamp = time.time()

    def to_dict(self):
        return {
            "sender": self.sender,
            "receiver": self.receiver,
            "amount": self.amount,
            "timestamp": self.timestamp
        }
    

class Client:
    def __init__(self, node_address: str):
        self.node_address = node_address

    def send_transaction(self, sender: str, receiver: str, amount: float):
        data = {
            "sender": sender,
            "receiver": receiver,
            "amount": amount
        }
        response = requests.post(f"http://{self.node_address}/add_transaction", json=data)
        return response.json()

    def get_blockchain(self):
        response = requests.get(f"http://{self.node_address}/get_chain")
        return response.json()
app = Flask(__name__)

# ─── 노드 정보 ───────────────────────────────────────────────

# 로컬 IP, 포트 결정
def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip

LOCAL_IP = get_local_ip()
LOCAL_PORT = os.getenv("PORT", "5001")

# 브로드캐스트로 (IP,PORT) 탐지
nodes = set()
BROADCAST_PORT = 5005
BROADCAST_INTERVAL = 5

def broadcast_presence() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    message = json.dumps({"ip": LOCAL_IP, "port": LOCAL_PORT})
    while True:
        sock.sendto(message.encode(), ('<broadcast>', BROADCAST_PORT))
        time.sleep(BROADCAST_INTERVAL)

def listen_for_nodes() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", BROADCAST_PORT))
    while True:
        try:
            data, _ = sock.recvfrom(1024)
            payload = json.loads(data.decode())
            peer_ip = payload.get("ip")
            peer_port = payload.get("port")
            if peer_ip and peer_port and (peer_ip, peer_port) != (LOCAL_IP, LOCAL_PORT):
                nodes.add((peer_ip, peer_port))
        except:
            continue

# 백그라운드 스레드 시작
threading.Thread(target=broadcast_presence, daemon=True).start()
threading.Thread(target=listen_for_nodes, daemon=True).start()
class Storage:
    def __init__(self, base_path: str = "./chunks"):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def save_chunk(self, chunk: bytes, node_id: str, chunk_index: int) -> None:
        node_folder = os.path.join(self.base_path, node_id)
        os.makedirs(node_folder, exist_ok=True)
        file_path = os.path.join(node_folder, f"chunk_{chunk_index}.bin")
        with open(file_path, "wb") as f:
            f.write(chunk)

    def retrieve_chunk(self, node_id: str, chunk_index: int) -> bytes:
        file_path = os.path.join(self.base_path, node_id, f"chunk_{chunk_index}.bin")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Chunk not found: {file_path}")
        with open(file_path, "rb") as f:
            return f.read()
class ErasureCode:
    def __init__(self, k: int = 4, n: int = 6):
        self.k = k  # 데이터 조각 수
        self.n = n  # 총 조각 수 (데이터 + 패리티)
        self.rsc = RSCodec(n - k)

    def encode(self, data: bytes, k: int = None, n: int = None):
        k = k or self.k
        n = n or self.n
        return self.rsc.encode(data)

    def decode(self, chunks: bytes):
        return self.rsc.decode(chunks)[0]

# ─── 블록체인·저장소 초기화 ─────────────────────────────────

blockchain = Blockchain()
storage = Storage()
erasure_code = ErasureCode()

# ─── REST API 엔드포인트 ────────────────────────────────────

@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    data = request.get_json()
    sender = data.get("sender")
    receiver = data.get("receiver")
    amount = data.get("amount")
    if not sender or not receiver or amount is None:
        return jsonify({"message": "Invalid transaction data"}), 400
    tx = Transaction(sender, receiver, amount)
    blockchain.pending_transactions.append(tx.to_dict())
    return jsonify({"message": "Transaction added"}), 201

@app.route('/mine', methods=['GET'])
def mine():
    if not blockchain.pending_transactions:
        return jsonify({"message": "No transactions to mine"}), 400
    new_block = blockchain.create_new_block()
    blockchain.add_block(new_block)
    # 소거 코드 인코딩 후 저장
    data_bytes = json.dumps(new_block.to_dict()).encode()
    encoded = erasure_code.encode(data_bytes)
    storage.save_chunk(encoded, LOCAL_IP, new_block.index)
    return jsonify({"message": "Block mined and stored", "block": new_block.to_dict()}), 200

@app.route('/get_chain', methods=['GET'])
def get_chain():
    chain_data = [block.to_dict() for block in blockchain.chain]
    return jsonify({"length": len(chain_data), "chain": chain_data}), 200

@app.route('/get_chunk/<int:block_index>', methods=['GET'])
def get_chunk(block_index: int):
    try:
        chunk_data = storage.retrieve_chunk(LOCAL_IP, block_index)
        return Response(chunk_data, status=200, content_type='application/octet-stream')
    except FileNotFoundError:
        return jsonify({"message": "Chunk not found"}), 404

@app.route('/get_nodes', methods=['GET'])
def get_nodes():
    # 탐지된 노드를 "ip:port" 문자열로 반환
    node_list = [f"{ip}:{port}" for ip, port in nodes]
    return jsonify({"nodes": node_list}), 200

@app.route('/sync_all', methods=['GET'])
def sync_all():
    synced = False
    # 체인 동기화
    for peer_ip, peer_port in nodes:
        try:
            r = requests.get(f"http://{peer_ip}:{peer_port}/get_chain")
            r_chain = r.json().get('chain', [])
            if len(r_chain) > len(blockchain.chain):
                blockchain.replace_chain(r_chain)
                synced = True
        except Exception as e:
            print(f"[ERROR] Chain sync failed from {peer_ip}:{peer_port} – {e}")
    # 청크 동기화
    for block in blockchain.chain:
        for peer_ip, peer_port in nodes:
            try:
                r = requests.get(f"http://{peer_ip}:{peer_port}/get_chunk/{block.index}")
                if r.status_code == 200:
                    storage.save_chunk(r.content, LOCAL_IP, block.index)
            except Exception as e:
                print(f"[ERROR] Chunk sync failed from {peer_ip}:{peer_port} – {e}")
    msg = 'Synchronization complete' + (' with updates' if synced else '')
    return jsonify({"message": msg}), 200
class Sync:
    def __init__(self, blockchain: Blockchain, storage: Storage, erasure_code: ErasureCode) -> None:
        self.blockchain = blockchain
        self.storage = storage
        self.erasure_code = erasure_code

    def sync_chain(self, target_node: str) -> bool:
        try:
            response = requests.get(f"http://{target_node}/get_chain")
            if response.status_code == 200:
                remote_chain = response.json().get("chain", [])
                if len(remote_chain) > len(self.blockchain.chain):
                    self.blockchain.replace_chain(remote_chain)
                    print("[INFO] Chain synchronized with node", target_node)
                    return True
        except Exception as e:
            print(f"[ERROR] Sync failed: {e}")
        return False

    def sync_storage(self, target_node: str) -> None:
        """
        지정된 노드에서 저장된 청크 데이터를 요청하고 복구
        """
        for block in self.blockchain.chain:
            try:
                response = requests.get(f"http://{target_node}/get_chunk/{block.index}")
                if response.status_code == 200:
                    encoded_chunk = response.content
                    decoded_data = self.erasure_code.decode(encoded_chunk)
                    print(f"[INFO] Block {block.index} recovered from node {target_node}")
                    self.storage.save_chunk(encoded_chunk, self.blockchain.node_id, block.index)
            except Exception as e:
                print(f"[ERROR] Storage sync failed for block {block.index}: {e}")

# ─── 서버 실행 ──────────────────────────────────────────────

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(LOCAL_PORT))

