import threading
import time
import socket
import json
import requests
from flask import Flask, request, jsonify, Response
from blockchain.blockchain import Blockchain
from blockchain.transaction import Transaction
from storage.storage import Storage
from storage.erasure_code import ErasureCode

app = Flask(__name__)

# 현재 노드의 IP 주소 얻기
def get_local_ip() -> str:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    ip = s.getsockname()[0]
    s.close()
    return ip

LOCAL_IP = get_local_ip()

# 네트워크 관리 (브로드캐스트 방식)
nodes = set()
BROADCAST_PORT = 5005
BROADCAST_INTERVAL = 5

def broadcast_presence() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    message = json.dumps({"ip": LOCAL_IP})
    while True:
        sock.sendto(message.encode(), ('<broadcast>', BROADCAST_PORT))
        time.sleep(BROADCAST_INTERVAL)

def listen_for_nodes() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", BROADCAST_PORT))
    while True:
        try:
            data, _ = sock.recvfrom(1024)
            payload = json.loads(data.decode())
            peer_ip = payload.get("ip")
            if peer_ip and peer_ip != LOCAL_IP:
                nodes.add(peer_ip)
        except:
            continue

# 스레드 시작
threading.Thread(target=broadcast_presence, daemon=True).start()
threading.Thread(target=listen_for_nodes, daemon=True).start()

# 인스턴스 생성
blockchain = Blockchain()
storage = Storage()
erasure_code = ErasureCode()

@app.route('/add_transaction', methods=['POST'])
def add_transaction() -> tuple[dict, int]:
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
def mine() -> tuple[dict, int]:
    if not blockchain.pending_transactions:
        return jsonify({"message": "No transactions to mine"}), 400

    new_block = blockchain.create_new_block()
    blockchain.add_block(new_block)

    data_bytes = json.dumps(new_block.to_dict()).encode()
    encoded = erasure_code.encode(data_bytes)
    storage.save_chunk(encoded, LOCAL_IP, new_block.index)

    return jsonify({"message": "Block mined and stored", "block": new_block.to_dict()}), 200

@app.route('/get_chain', methods=['GET'])
def get_chain() -> tuple[dict, int]:
    chain_data = [block.to_dict() for block in blockchain.chain]
    return jsonify({"length": len(chain_data), "chain": chain_data}), 200

@app.route('/get_chunk/<int:block_index>', methods=['GET'])
def get_chunk(block_index: int) -> Response:
    try:
        chunk_data = storage.retrieve_chunk(LOCAL_IP, block_index)
        return Response(chunk_data, status=200, content_type='application/octet-stream')
    except FileNotFoundError:
        return jsonify({"message": "Chunk not found"}), 404

@app.route('/get_nodes', methods=['GET'])
def get_nodes() -> tuple[dict, int]:
    return jsonify({"nodes": list(nodes)}), 200

@app.route('/sync_all', methods=['GET'])
def sync_all() -> tuple[dict, int]:
    synced = False
    for peer_ip in nodes:
        try:
            r_chain = requests.get(f"http://{peer_ip}:5000/get_chain").json().get('chain', [])
            if len(r_chain) > len(blockchain.chain):
                blockchain.replace_chain(r_chain)
                synced = True
        except:
            continue
    for block in blockchain.chain:
        for peer_ip in nodes:
            try:
                r = requests.get(f"http://{peer_ip}:5000/get_chunk/{block.index}")
                if r.status_code == 200:
                    storage.save_chunk(r.content, LOCAL_IP, block.index)
            except:
                continue
    msg = 'Synchronization complete' + (' with updates' if synced else '')
    return jsonify({"message": msg}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
