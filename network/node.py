import os, time
import json
import threading
import socket, requests
from flask import Flask, request, jsonify, Response

from blockchain.blockchain import Blockchain
from blockchain.transaction import Transaction
from storage import Storage, ErasureCode

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
LOCAL_PORT = os.getenv("PORT", "5000")

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
        print(f"[DEBUG] Broadcasting {message}")
        time.sleep(BROADCAST_INTERVAL)

def listen_for_nodes() -> None:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("", BROADCAST_PORT))
    print(f"[DEBUG] Listening on UDP port {BROADCAST_PORT}")
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            print(f"[DEBUG] Received raw packet from {addr}: {data}")
            payload = json.loads(data.decode())
            peer_ip = payload.get("ip")
            if peer_ip and peer_ip != LOCAL_IP:
                nodes.add(peer_ip)
                print(f"[DEBUG] Added peer {peer_ip}, nodes = {nodes}")
        except Exception as e:
            print("[DEBUG] Error receiving broadcast:", e)
            continue

# 백그라운드 스레드 시작
threading.Thread(target=broadcast_presence, daemon=True).start()
threading.Thread(target=listen_for_nodes, daemon=True).start()

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
    encoded = bytes(erasure_code.encode(data_bytes))
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

# ─── 서버 실행 ──────────────────────────────────────────────

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(LOCAL_PORT))
