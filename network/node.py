import os, time
import json
import threading
import socket, requests
from flask import Flask, request, jsonify, Response, render_template

from blockchain.blockchain import Blockchain
from blockchain.transaction import Transaction
from storage import Storage, ErasureCode

# 템플릿과 정적 파일 경로 설정 (프로젝트 루트 기준)
# node.py가 network/ 디렉토리에 있으므로, 상위 디렉토리가 프로젝트 루트
current_file = os.path.abspath(__file__)
network_dir = os.path.dirname(current_file)
base_dir = os.path.dirname(network_dir)  # 프로젝트 루트

template_dir = os.path.join(base_dir, 'templates')
static_dir = os.path.join(base_dir, 'static')

# 경로 확인 및 생성
if not os.path.exists(template_dir):
    os.makedirs(template_dir, exist_ok=True)
    print(f"[WARN] Created template directory: {template_dir}")
if not os.path.exists(static_dir):
    os.makedirs(static_dir, exist_ok=True)
    print(f"[WARN] Created static directory: {static_dir}")

print(f"[INFO] Template directory: {template_dir} (exists: {os.path.exists(template_dir)})")
print(f"[INFO] Static directory: {static_dir} (exists: {os.path.exists(static_dir)})")

app = Flask(__name__, 
            template_folder=template_dir, 
            static_folder=static_dir,
            static_url_path='/static')

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
nodes = {}  # {ip: port} 형태로 저장
BROADCAST_PORT_BASE = 5005  # 기본 포트
BROADCAST_PORT = None  # 실제 사용할 포트 (동적으로 결정)
BROADCAST_INTERVAL = 5

def find_available_port(start_port: int, max_attempts: int = 10) -> int:
    """사용 가능한 포트를 찾습니다."""
    for i in range(max_attempts):
        port = start_port + i
        try:
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            test_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            test_sock.bind(("", port))
            test_sock.close()
            return port
        except OSError:
            continue
    # 모든 포트가 사용 중이면 기본 포트 반환 (에러는 나중에 처리)
    return start_port

def broadcast_presence() -> None:
    global BROADCAST_PORT
    
    # 포트가 아직 결정되지 않았으면 잠시 대기
    if BROADCAST_PORT is None:
        time.sleep(1)  # listen_for_nodes가 포트를 결정할 시간을 줌
        if BROADCAST_PORT is None:
            BROADCAST_PORT = BROADCAST_PORT_BASE
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    except Exception as e:
        print(f"[WARN] Failed to configure broadcast socket: {e}")
        return
    
    message = json.dumps({"ip": LOCAL_IP, "port": LOCAL_PORT})
    while True:
        try:
            # 브로드캐스트 전송 (255.255.255.255 사용)
            sock.sendto(message.encode(), ('255.255.255.255', BROADCAST_PORT))
            # print(f"[DEBUG] Broadcasting {message} on port {BROADCAST_PORT}")  # 너무 많은 로그 방지
        except Exception as e:
            print(f"[WARN] Broadcast failed on port {BROADCAST_PORT}: {e}")
        time.sleep(BROADCAST_INTERVAL)

def listen_for_nodes() -> None:
    global BROADCAST_PORT
    
    # 사용 가능한 포트 찾기
    if BROADCAST_PORT is None:
        BROADCAST_PORT = find_available_port(BROADCAST_PORT_BASE)
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind(("", BROADCAST_PORT))
        print(f"[INFO] Listening on UDP port {BROADCAST_PORT} for node discovery")
    except OSError as e:
        # 포트가 사용 중이면 다른 포트 시도
        if e.winerror == 10048 or (hasattr(e, 'errno') and e.errno == 98):  # Windows/Linux: 포트 사용 중
            print(f"[WARN] Port {BROADCAST_PORT} is already in use. Trying alternative port...")
            BROADCAST_PORT = find_available_port(BROADCAST_PORT_BASE + 1)
            try:
                sock.close()
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("", BROADCAST_PORT))
                print(f"[INFO] Successfully bound to alternative port {BROADCAST_PORT}")
            except OSError as e2:
                print(f"[WARN] Failed to bind to alternative port {BROADCAST_PORT}: {e2}")
                print(f"[WARN] Node discovery disabled. GUI and other features will still work normally.")
                return
        else:
            print(f"[ERROR] Failed to bind to port {BROADCAST_PORT}: {e}")
            return
    
    while True:
        try:
            data, addr = sock.recvfrom(1024)
            print(f"[DEBUG] Received raw packet from {addr}: {data}")
            payload = json.loads(data.decode())
            peer_ip = payload.get("ip")
            peer_port = payload.get("port")
            if peer_ip and peer_ip != LOCAL_IP and peer_port:
                # 노드 추가 및 업데이트
                old_port = nodes.get(peer_ip)
                nodes[peer_ip] = peer_port
                if old_port != peer_port:
                    print(f"[INFO] Added/Updated peer {peer_ip}:{peer_port}, nodes = {nodes}")
                # 첫 번째 발견 시에도 로그 출력 (디버깅용)
                elif old_port is None:
                    print(f"[INFO] Discovered peer {peer_ip}:{peer_port}, nodes = {nodes}")
        except json.JSONDecodeError as e:
            print(f"[DEBUG] Invalid JSON in broadcast packet: {e}")
            continue
        except Exception as e:
            print(f"[DEBUG] Error receiving broadcast: {e}")
            continue

# ─── 자동 동기화 및 알림 함수 ────────────────────────────────

def notify_new_block(block_data: dict) -> None:
    """
    다른 노드들에게 새 블록이 채굴되었음을 알립니다.
    """
    for peer_ip, peer_port in nodes.items():
        try:
            requests.post(
                f"http://{peer_ip}:{peer_port}/notify_new_block",
                json={"block": block_data},
                timeout=5
            )
            print(f"[INFO] Notified {peer_ip}:{peer_port} about new block")
        except Exception as e:
            print(f"[WARN] Failed to notify {peer_ip}:{peer_port} about new block: {e}")

def auto_sync_chain() -> None:
    """
    주기적으로 체인을 자동 동기화하는 백그라운드 스레드
    """
    while True:
        try:
            time.sleep(10)  # 10초마다 체인 확인
            if not nodes:
                continue  # 연결된 노드가 없으면 스킵
            
            # 각 노드의 체인 길이 확인
            for peer_ip, peer_port in nodes.items():
                try:
                    r = requests.get(f"http://{peer_ip}:{peer_port}/get_chain", timeout=10)
                    if r.status_code == 200:
                        r_chain = r.json().get('chain', [])
                        if len(r_chain) > len(blockchain.chain):
                            # 더 긴 체인 발견 - 동기화 수행
                            print(f"[INFO] Auto-syncing chain from {peer_ip}:{peer_port} (length: {len(r_chain)} vs {len(blockchain.chain)})")
                            # 동기화 전에 원격 체인의 유효성 검증
                            from blockchain.block import Block
                            temp_chain = []
                            for block_data in r_chain:
                                block = Block(
                                    index=block_data['index'],
                                    previous_hash=block_data['previous_hash'],
                                    timestamp=block_data['timestamp'],
                                    transactions=block_data['transactions'],
                                    nonce=block_data.get('nonce', 0)
                                )
                                block.hash = block_data['hash']
                                temp_chain.append(block)
                            
                            # 임시 체인의 유효성 검증
                            is_valid = True
                            for i in range(1, len(temp_chain)):
                                current = temp_chain[i]
                                prev = temp_chain[i-1]
                                if current.hash != current.calculate_hash():
                                    is_valid = False
                                    break
                                if current.previous_hash != prev.hash:
                                    is_valid = False
                                    break
                            
                            if is_valid:
                                blockchain.replace_chain(r_chain)
                                # 동기화된 블록들의 메타데이터 저장
                                for block_data in r_chain:
                                    block_index = block_data.get('index', -1)
                                    if block_index > 0:  # Genesis 블록 제외
                                        block_metadata = {
                                            "hash": block_data.get('hash', ''),
                                            "timestamp": block_data.get('timestamp', 0),
                                            "nonce": block_data.get('nonce', 0),
                                            "previous_hash": block_data.get('previous_hash', '')
                                        }
                                        storage.save_block_metadata(LOCAL_IP, block_index, block_metadata)
                                print(f"[INFO] Auto-sync completed from {peer_ip}:{peer_port}")
                            else:
                                print(f"[WARN] Rejected invalid chain from {peer_ip}:{peer_port} during auto-sync")
                except Exception as e:
                    # 네트워크 오류는 무시 (일시적일 수 있음)
                    continue
        except Exception as e:
            print(f"[ERROR] Auto-sync error: {e}")
            time.sleep(5)  # 오류 발생 시 5초 대기 후 재시도

# 백그라운드 스레드 시작
threading.Thread(target=broadcast_presence, daemon=True).start()
threading.Thread(target=listen_for_nodes, daemon=True).start()
threading.Thread(target=auto_sync_chain, daemon=True).start()

# ─── 블록체인·저장소 초기화 ─────────────────────────────────

blockchain = Blockchain()
storage = Storage()
erasure_code = ErasureCode()

# 로컬에서 채굴한 블록 인덱스 추적 (트랜잭션 표시용)
local_mined_blocks = set()  # {block_index, ...}

def restore_chain_from_chunks() -> None:
    """
    프로그램 시작 시 저장된 청크 파일에서 블록을 복구하여 체인에 추가합니다.
    현재 IP의 청크만 복구합니다.
    """
    try:
        # 현재 IP의 청크 목록 조회
        chunks = storage.list_chunks(node_id=LOCAL_IP)
        if not chunks:
            print("[INFO] No chunks found to restore")
            return
        
        # 블록 인덱스별로 그룹화
        blocks_map = {}
        for chunk in chunks:
            block_index = chunk["block_index"]
            if block_index == 0:
                continue  # Genesis 블록은 건너뛰기
            
            if block_index not in blocks_map:
                blocks_map[block_index] = []
            blocks_map[block_index].append(chunk["chunk_id"])
        
        # 각 블록에 대해 k개 이상의 청크가 있는지 확인하고 복구
        restored_count = 0
        for block_index in sorted(blocks_map.keys()):
            # 체인에 이미 있는 블록은 건너뛰기
            if block_index < len(blockchain.chain):
                continue
            
            chunk_ids = blocks_map[block_index]
            if len(chunk_ids) >= erasure_code.k:
                # k개 이상의 청크가 있으면 복구 시도
                try:
                    chunks_data = {}
                    for chunk_id in chunk_ids[:erasure_code.k]:  # k개만 사용
                        chunk_data = storage.retrieve_chunk(LOCAL_IP, block_index, chunk_id=chunk_id)
                        chunks_data[chunk_id] = chunk_data
                    
                    # 청크를 리스트로 변환 (chunk_id 순서대로)
                    chunk_list = [chunks_data[i] for i in sorted(chunks_data.keys())[:erasure_code.k]]
                    
                    # 소거 코드 디코딩하여 원본 데이터 복구
                    recovered_data = erasure_code.decode(chunk_list)
                    recovered_block_dict = json.loads(recovered_data.decode())
                    
                    # 블록 객체 생성
                    from blockchain.block import Block
                    recovered_block = Block(
                        index=recovered_block_dict['index'],
                        previous_hash=recovered_block_dict['previous_hash'],
                        timestamp=recovered_block_dict['timestamp'],
                        transactions=recovered_block_dict.get('transactions', []),
                        nonce=recovered_block_dict.get('nonce', 0)
                    )
                    recovered_block.hash = recovered_block_dict['hash']
                    
                    # 체인에 추가 (유효성 검증 후)
                    if len(blockchain.chain) == recovered_block.index:
                        # 이전 블록의 해시가 일치하는지 확인
                        if recovered_block.previous_hash == blockchain.chain[-1].hash:
                            blockchain.chain.append(recovered_block)
                            restored_count += 1
                            print(f"[INFO] Restored block {block_index} from chunks")
                        else:
                            print(f"[WARN] Block {block_index} previous_hash mismatch, skipping")
                    elif recovered_block.index < len(blockchain.chain):
                        # 이미 체인에 있는 블록은 건너뛰기
                        pass
                    else:
                        print(f"[WARN] Block {block_index} index mismatch (expected {len(blockchain.chain)}), skipping")
                        
                except Exception as e:
                    print(f"[WARN] Failed to restore block {block_index} from chunks: {e}")
                    continue
        
        if restored_count > 0:
            print(f"[INFO] Restored {restored_count} blocks from chunks")
        else:
            print("[INFO] No blocks restored from chunks")
            
    except Exception as e:
        print(f"[ERROR] Failed to restore chain from chunks: {e}")
        import traceback
        traceback.print_exc()

# 프로그램 시작 시 저장된 청크에서 블록 복구
restore_chain_from_chunks()

# ─── 합의 및 검증 헬퍼 함수 ──────────────────────────────────

def check_chain_consensus() -> tuple[bool, str]:
    """
    다른 노드들과의 체인 일치 여부를 확인합니다.
    더 긴 체인이 있으면 먼저 동기화를 시도합니다.
    :return: (일치 여부, 메시지)
    """
    if not nodes:
        # 연결된 노드가 없으면 검증 불가 (허용)
        return True, "No connected nodes to verify against"
    
    local_chain_length = len(blockchain.chain)
    local_chain_hash = blockchain.chain[-1].hash if blockchain.chain else ""
    
    # 먼저 더 긴 체인이 있는지 확인하고 동기화 시도
    longer_chain_found = False
    for peer_ip, peer_port in nodes.items():
        try:
            r = requests.get(f"http://{peer_ip}:{peer_port}/get_chain", timeout=10)
            if r.status_code == 200:
                peer_data = r.json()
                peer_chain = peer_data.get('chain', [])
                peer_chain_length = len(peer_chain)
                
                # 더 긴 체인이 있으면 동기화 시도
                if peer_chain_length > local_chain_length:
                    longer_chain_found = True
                    print(f"[INFO] Longer chain found at {peer_ip}:{peer_port} ({peer_chain_length} vs {local_chain_length}), attempting sync...")
                    
                    # 동기화 전에 원격 체인의 유효성 검증
                    from blockchain.block import Block
                    temp_chain = []
                    for block_data in peer_chain:
                        block = Block(
                            index=block_data['index'],
                            previous_hash=block_data['previous_hash'],
                            timestamp=block_data['timestamp'],
                            transactions=block_data['transactions'],
                            nonce=block_data.get('nonce', 0)
                        )
                        block.hash = block_data['hash']
                        temp_chain.append(block)
                    
                    # 임시 체인의 유효성 검증
                    is_valid = True
                    for i in range(1, len(temp_chain)):
                        current = temp_chain[i]
                        prev = temp_chain[i-1]
                        if current.hash != current.calculate_hash():
                            is_valid = False
                            break
                        if current.previous_hash != prev.hash:
                            is_valid = False
                            break
                    
                    if is_valid:
                        blockchain.replace_chain(peer_chain)
                        print(f"[INFO] Chain synchronized from {peer_ip}:{peer_port} during consensus check")
                        # 동기화 후 다시 체인 길이와 해시 확인
                        local_chain_length = len(blockchain.chain)
                        local_chain_hash = blockchain.chain[-1].hash if blockchain.chain else ""
                        break  # 동기화 완료, 다시 검증
        except Exception as e:
            print(f"[WARN] Failed to check chain from {peer_ip}:{peer_port}: {e}")
            continue
    
    # 동기화 후 다시 일치 여부 확인
    mismatched_nodes = []
    for peer_ip, peer_port in nodes.items():
        try:
            r = requests.get(f"http://{peer_ip}:{peer_port}/get_chain", timeout=10)
            if r.status_code == 200:
                peer_data = r.json()
                peer_chain = peer_data.get('chain', [])
                peer_chain_length = len(peer_chain)
                peer_chain_hash = peer_chain[-1].hash if peer_chain else ""
                
                # 체인 길이와 마지막 블록 해시 비교
                if peer_chain_length != local_chain_length:
                    mismatched_nodes.append(f"{peer_ip}:{peer_port} (length: {peer_chain_length} vs {local_chain_length})")
                elif peer_chain_hash != local_chain_hash:
                    mismatched_nodes.append(f"{peer_ip}:{peer_port} (hash mismatch)")
        except Exception as e:
            print(f"[WARN] Failed to check chain from {peer_ip}:{peer_port}: {e}")
            # 네트워크 오류는 일치하지 않는 것으로 간주하지 않음 (일시적 오류일 수 있음)
            continue
    
    if mismatched_nodes:
        return False, f"Chain mismatch detected with nodes: {', '.join(mismatched_nodes)}"
    
    return True, "Chain consensus verified"

def validate_chain_before_operation() -> tuple[bool, str]:
    """
    거래 추가나 블록 채굴 전에 체인 유효성과 일치성을 검증합니다.
    :return: (유효 여부, 메시지)
    """
    # 1. 로컬 체인 유효성 검증
    if not blockchain.is_chain_valid():
        return False, "Local chain is invalid"
    
    # 2. 다른 노드들과의 일치 여부 확인
    consensus_ok, consensus_msg = check_chain_consensus()
    if not consensus_ok:
        return False, consensus_msg
    
    return True, "Chain validation passed"

# ─── REST API 엔드포인트 ────────────────────────────────────

@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    # 거래 추가 전 체인 검증
    is_valid, validation_msg = validate_chain_before_operation()
    if not is_valid:
        print(f"[WARN] Transaction rejected due to chain validation failure: {validation_msg}")
        return jsonify({
            "message": f"Transaction rejected: {validation_msg}",
            "error": "CHAIN_VALIDATION_FAILED"
        }), 403  # 403 Forbidden: 거래가 차단됨
    
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
    
    # 블록 채굴 전 체인 검증
    is_valid, validation_msg = validate_chain_before_operation()
    if not is_valid:
        print(f"[WARN] Mining rejected due to chain validation failure: {validation_msg}")
        return jsonify({
            "message": f"Mining rejected: {validation_msg}",
            "error": "CHAIN_VALIDATION_FAILED"
        }), 403  # 403 Forbidden: 채굴이 차단됨
    
    new_block = blockchain.create_new_block()
    blockchain.add_block(new_block)
    
    # 로컬에서 채굴한 블록 인덱스 저장
    local_mined_blocks.add(new_block.index)
    
    # 소거 코드 인코딩하여 n개 청크로 분할
    chunks = blockchain.store_block(new_block)
    
    # 자신 포함하여 사용 가능한 노드 목록 생성
    available_nodes = [(LOCAL_IP, LOCAL_PORT)] + list(nodes.items())
    
    # 블록 메타데이터 저장 (해시, 타임스탬프, nonce, previous_hash)
    block_metadata = {
        "hash": new_block.hash,
        "timestamp": new_block.timestamp,
        "nonce": new_block.nonce,
        "previous_hash": new_block.previous_hash
    }
    storage.save_block_metadata(LOCAL_IP, new_block.index, block_metadata)
    
    # 6개 청크를 각 노드에 1개씩 분산 저장
    distributed = 0
    for i, chunk in enumerate(chunks):
        if i < len(available_nodes):
            target_ip, target_port = available_nodes[i]
            if target_ip == LOCAL_IP:
                # 로컬 저장
                storage.save_chunk(chunk, LOCAL_IP, new_block.index, chunk_id=i)
                distributed += 1
            else:
                # 원격 노드에 저장 요청
                try:
                    response = requests.post(
                        f"http://{target_ip}:{target_port}/store_chunk/{new_block.index}/{i}",
                        data=chunk,
                        headers={'Content-Type': 'application/octet-stream'},
                        timeout=30
                    )
                    if response.status_code == 200:
                        distributed += 1
                        print(f"[INFO] Chunk {i} stored on {target_ip}:{target_port}")
                    else:
                        print(f"[WARN] Failed to store chunk {i} on {target_ip}:{target_port}")
                except Exception as e:
                    print(f"[ERROR] Failed to store chunk {i} on {target_ip}:{target_port}: {e}")
    
    # 다른 노드들에게 새 블록 알림 전송 (메타데이터 포함)
    block_dict = new_block.to_dict()
    notify_new_block(block_dict)
    
    return jsonify({
        "message": f"Block mined and distributed ({distributed}/{len(chunks)} chunks)",
        "block": block_dict
    }), 200

@app.route('/get_chain', methods=['GET'])
def get_chain():
    chain_data = [block.to_dict() for block in blockchain.chain]
    
    # 현재 IP의 청크가 있는 블록 인덱스 확인 (체인에 없어도 표시하기 위해)
    chunks = storage.list_chunks(node_id=LOCAL_IP)
    chunk_block_indices = set()
    for chunk in chunks:
        if chunk["block_index"] > 0:  # Genesis 블록 제외
            chunk_block_indices.add(chunk["block_index"])
    
    # 체인에 없는 블록 중 청크가 있는 블록의 메타데이터 조회 (복구 없이)
    additional_blocks = []
    for block_index in chunk_block_indices:
        # 체인에 이미 있는 블록은 건너뛰기
        if block_index < len(chain_data):
            continue
        
        # 메타데이터 조회 (복구 없이)
        metadata = storage.get_block_metadata(LOCAL_IP, block_index)
        if metadata:
            # 메타데이터가 있으면 블록 정보 생성 (트랜잭션은 숨김)
            additional_blocks.append({
                "index": block_index,
                "previous_hash": metadata.get('previous_hash', ''),
                "timestamp": metadata.get('timestamp', 0),
                "transactions": [],  # 트랜잭션은 숨김
                "nonce": metadata.get('nonce', 0),
                "hash": metadata.get('hash', ''),
                "from_chunks": True  # 청크에서 온 블록임을 표시 (복구되지 않음)
            })
    
    # 체인 데이터와 추가 블록 합치기
    all_blocks = chain_data + additional_blocks
    
    # 로컬에서 채굴한 블록 인덱스 정보 추가
    return jsonify({
        "length": len(chain_data),  # 실제 체인 길이
        "chain": all_blocks,  # 체인 + 청크만 있는 블록
        "local_mined_blocks": list(local_mined_blocks)  # 로컬에서 채굴한 블록 인덱스 리스트
    }), 200

@app.route('/get_chunk/<int:block_index>', methods=['GET'])
def get_chunk(block_index: int):
    """기존 호환성을 위한 엔드포인트 (chunk_id=0 사용)"""
    try:
        chunk_data = storage.retrieve_chunk(LOCAL_IP, block_index, chunk_id=0)
        return Response(chunk_data, status=200, content_type='application/octet-stream')
    except FileNotFoundError:
        return jsonify({"message": "Chunk not found"}), 404

@app.route('/get_chunk/<int:block_index>/<int:chunk_id>', methods=['GET'])
def get_chunk_by_id(block_index: int, chunk_id: int):
    """특정 청크 ID로 청크 조회"""
    try:
        chunk_data = storage.retrieve_chunk(LOCAL_IP, block_index, chunk_id=chunk_id)
        return Response(chunk_data, status=200, content_type='application/octet-stream')
    except FileNotFoundError:
        return jsonify({"message": f"Chunk {chunk_id} not found for block {block_index}"}), 404

@app.route('/store_chunk/<int:block_index>/<int:chunk_id>', methods=['POST'])
def store_chunk(block_index: int, chunk_id: int):
    """다른 노드로부터 청크 저장 요청 수신"""
    try:
        chunk_data = request.data
        storage.save_chunk(chunk_data, LOCAL_IP, block_index, chunk_id=chunk_id)
        print(f"[INFO] Received and stored chunk {chunk_id} for block {block_index}")
        return jsonify({"message": f"Chunk {chunk_id} stored for block {block_index}"}), 200
    except Exception as e:
        print(f"[ERROR] Failed to store chunk {chunk_id} for block {block_index}: {e}")
        return jsonify({"message": "Failed to store chunk"}), 500

@app.route('/get_nodes', methods=['GET'])
def get_nodes():
    # 탐지된 노드를 "ip:port" 문자열로 반환
    node_list = [f"{ip}:{port}" for ip, port in nodes.items()]
    return jsonify({"nodes": node_list}), 200

@app.route('/notify_new_block', methods=['POST'])
def notify_new_block_endpoint():
    """
    다른 노드로부터 새 블록 알림을 받습니다.
    알림을 받으면 자동으로 체인을 동기화합니다.
    메타데이터도 함께 저장합니다.
    """
    try:
        data = request.get_json()
        block_data = data.get('block')
        if not block_data:
            return jsonify({"message": "No block data provided"}), 400
        
        # 블록 메타데이터 저장 (다른 노드에서 채굴한 블록)
        block_index = block_data.get('index', -1)
        if block_index > 0:  # Genesis 블록 제외
            block_metadata = {
                "hash": block_data.get('hash', ''),
                "timestamp": block_data.get('timestamp', 0),
                "nonce": block_data.get('nonce', 0),
                "previous_hash": block_data.get('previous_hash', '')
            }
            # 알림을 보낸 노드의 IP 확인
            sender_ip = request.remote_addr
            if sender_ip and sender_ip.startswith('::ffff:'):
                sender_ip = sender_ip[7:]  # IPv4-mapped IPv6 주소 처리
            
            # 메타데이터를 로컬에 저장 (sender_ip 대신 LOCAL_IP에 저장하여 현재 IP의 청크로 관리)
            # 하지만 실제로는 sender_ip를 사용해야 할 수도 있음. 일단 LOCAL_IP에 저장
            storage.save_block_metadata(LOCAL_IP, block_index, block_metadata)
        
        # 알림을 받은 블록이 로컬 체인보다 새로운지 확인
        if block_index > len(blockchain.chain) - 1:
            # 새 블록이 발견됨 - 체인 동기화 수행
            print(f"[INFO] Received new block notification: block #{block_index}")
            
            # 알림을 보낸 노드의 IP 확인 (request.remote_addr 사용)
            sender_ip = request.remote_addr
            if sender_ip and sender_ip.startswith('::ffff:'):
                sender_ip = sender_ip[7:]  # IPv4-mapped IPv6 주소 처리
            
            # 알림을 보낸 노드가 nodes에 있으면 해당 노드에서 먼저 체인 가져오기
            sync_attempted = False
            if sender_ip and sender_ip in nodes:
                sender_port = nodes[sender_ip]
                try:
                    r = requests.get(f"http://{sender_ip}:{sender_port}/get_chain", timeout=10)
                    if r.status_code == 200:
                        r_chain = r.json().get('chain', [])
                        if len(r_chain) > len(blockchain.chain):
                            sync_attempted = True
                            # 동기화 전에 원격 체인의 유효성 검증
                            from blockchain.block import Block
                            temp_chain = []
                            for b_data in r_chain:
                                block = Block(
                                    index=b_data['index'],
                                    previous_hash=b_data['previous_hash'],
                                    timestamp=b_data['timestamp'],
                                    transactions=b_data['transactions'],
                                    nonce=b_data.get('nonce', 0)
                                )
                                block.hash = b_data['hash']
                                temp_chain.append(block)
                            
                            # 임시 체인의 유효성 검증
                            is_valid = True
                            for i in range(1, len(temp_chain)):
                                current = temp_chain[i]
                                prev = temp_chain[i-1]
                                if current.hash != current.calculate_hash():
                                    is_valid = False
                                    break
                                if current.previous_hash != prev.hash:
                                    is_valid = False
                                    break
                            
                            if is_valid:
                                blockchain.replace_chain(r_chain)
                                # 동기화된 블록들의 메타데이터 저장
                                for b_data in r_chain:
                                    b_index = b_data.get('index', -1)
                                    if b_index > 0:  # Genesis 블록 제외
                                        b_metadata = {
                                            "hash": b_data.get('hash', ''),
                                            "timestamp": b_data.get('timestamp', 0),
                                            "nonce": b_data.get('nonce', 0),
                                            "previous_hash": b_data.get('previous_hash', '')
                                        }
                                        storage.save_block_metadata(LOCAL_IP, b_index, b_metadata)
                                print(f"[INFO] Chain synchronized from notification sender {sender_ip}:{sender_port} (new length: {len(r_chain)})")
                                return jsonify({"message": "Notification received and chain synchronized"}), 200
                except Exception as e:
                    print(f"[WARN] Failed to sync from notification sender {sender_ip}:{sender_port}: {e}")
            
            # 알림을 보낸 노드에서 동기화 실패 시, 다른 모든 노드에서 체인 확인하여 동기화
            for peer_ip, peer_port in nodes.items():
                try:
                    r = requests.get(f"http://{peer_ip}:{peer_port}/get_chain", timeout=10)
                    if r.status_code == 200:
                        r_chain = r.json().get('chain', [])
                        if len(r_chain) > len(blockchain.chain):
                            # 동기화 전에 원격 체인의 유효성 검증
                            from blockchain.block import Block
                            temp_chain = []
                            for b_data in r_chain:
                                block = Block(
                                    index=b_data['index'],
                                    previous_hash=b_data['previous_hash'],
                                    timestamp=b_data['timestamp'],
                                    transactions=b_data['transactions'],
                                    nonce=b_data.get('nonce', 0)
                                )
                                block.hash = b_data['hash']
                                temp_chain.append(block)
                            
                            # 임시 체인의 유효성 검증
                            is_valid = True
                            for i in range(1, len(temp_chain)):
                                current = temp_chain[i]
                                prev = temp_chain[i-1]
                                if current.hash != current.calculate_hash():
                                    is_valid = False
                                    break
                                if current.previous_hash != prev.hash:
                                    is_valid = False
                                    break
                            
                            if is_valid:
                                blockchain.replace_chain(r_chain)
                                print(f"[INFO] Chain synchronized from notification (new length: {len(r_chain)})")
                                # 체인 동기화 완료 - GUI가 자동으로 새로고침하도록 체인 길이 변경 감지
                                break  # 동기화 완료
                except Exception as e:
                    continue  # 다음 노드 시도
        
        return jsonify({"message": "Notification received"}), 200
    except Exception as e:
        print(f"[ERROR] Failed to process new block notification: {e}")
        return jsonify({"message": "Failed to process notification"}), 500

@app.route('/sync_all', methods=['GET'])
def sync_all():
    synced = False
    # 체인 동기화
    for peer_ip, peer_port in nodes.items():
        try:
            r = requests.get(f"http://{peer_ip}:{peer_port}/get_chain", timeout=30)
            r_chain = r.json().get('chain', [])
            if len(r_chain) > len(blockchain.chain):
                # 동기화 전에 원격 체인의 유효성 검증
                # 임시로 체인을 교체하여 검증
                from blockchain.block import Block
                temp_chain = []
                for block_data in r_chain:
                    block = Block(
                        index=block_data['index'],
                        previous_hash=block_data['previous_hash'],
                        timestamp=block_data['timestamp'],
                        transactions=block_data['transactions'],
                        nonce=block_data.get('nonce', 0)
                    )
                    block.hash = block_data['hash']
                    temp_chain.append(block)
                
                # 임시 체인의 유효성 검증
                is_valid = True
                for i in range(1, len(temp_chain)):
                    current = temp_chain[i]
                    prev = temp_chain[i-1]
                    if current.hash != current.calculate_hash():
                        is_valid = False
                        break
                    if current.previous_hash != prev.hash:
                        is_valid = False
                        break
                
                if is_valid:
                    blockchain.replace_chain(r_chain)
                    # 동기화된 블록들의 메타데이터 저장
                    for block_data in r_chain:
                        block_index = block_data.get('index', -1)
                        if block_index > 0:  # Genesis 블록 제외
                            block_metadata = {
                                "hash": block_data.get('hash', ''),
                                "timestamp": block_data.get('timestamp', 0),
                                "nonce": block_data.get('nonce', 0),
                                "previous_hash": block_data.get('previous_hash', '')
                            }
                            storage.save_block_metadata(LOCAL_IP, block_index, block_metadata)
                    synced = True
                    print(f"[INFO] Chain synchronized and validated from {peer_ip}:{peer_port}")
                else:
                    print(f"[WARN] Rejected invalid chain from {peer_ip}:{peer_port}")
        except Exception as e:
            print(f"[ERROR] Chain sync failed from {peer_ip}:{peer_port} – {e}")
    # 청크 동기화 (기존 방식 - 호환성 유지)
    for block in blockchain.chain:
        for peer_ip, peer_port in nodes.items():
            try:
                r = requests.get(f"http://{peer_ip}:{peer_port}/get_chunk/{block.index}", timeout=30)
                if r.status_code == 200:
                    storage.save_chunk(r.content, LOCAL_IP, block.index, chunk_id=0)
            except Exception as e:
                print(f"[ERROR] Chunk sync failed from {peer_ip}:{peer_port} – {e}")
    msg = 'Synchronization complete' + (' with updates' if synced else '')
    return jsonify({"message": msg}), 200

@app.route('/recover_block/<int:block_index>', methods=['GET'])
def recover_block(block_index: int):
    """
    분산 저장된 청크를 수집하여 블록 복구
    네트워크에 자신 포함 4개 이상 접속 시 복구 가능, 30초 타임아웃
    """
    # 자신 포함하여 사용 가능한 노드 목록 생성
    available_nodes = [(LOCAL_IP, LOCAL_PORT)] + list(nodes.items())
    total_nodes = len(available_nodes)
    
    if total_nodes < erasure_code.k:
        print(f"[WARN] Not enough nodes for recovery: {total_nodes} < {erasure_code.k}")
        return jsonify({
            "message": f"Insufficient nodes for recovery: {total_nodes} < {erasure_code.k}",
            "available_nodes": total_nodes
        }), 400
    
    # n개 청크 수집 시도 (k=2개 이상이면 복구 가능)
    chunks = {}
    collected_chunks = 0
    
    for chunk_id in range(erasure_code.n):
        for node_ip, node_port in available_nodes:
            if chunk_id in chunks:
                break  # 이미 수집한 청크는 건너뛰기
            
            try:
                if node_ip == LOCAL_IP:
                    # 로컬에서 조회
                    if storage.has_chunk(LOCAL_IP, block_index, chunk_id=chunk_id):
                        chunks[chunk_id] = storage.retrieve_chunk(LOCAL_IP, block_index, chunk_id=chunk_id)
                        collected_chunks += 1
                        print(f"[INFO] Collected chunk {chunk_id} from local storage")
                else:
                    # 원격 노드에서 조회
                    r = requests.get(
                        f"http://{node_ip}:{node_port}/get_chunk/{block_index}/{chunk_id}",
                        timeout=30
                    )
                    if r.status_code == 200:
                        chunks[chunk_id] = r.content
                        collected_chunks += 1
                        print(f"[INFO] Collected chunk {chunk_id} from {node_ip}:{node_port}")
                        break
            except Exception as e:
                print(f"[DEBUG] Failed to get chunk {chunk_id} from {node_ip}:{node_port}: {e}")
                continue
    
    # 최소 k개 청크가 수집되었는지 확인
    if collected_chunks < erasure_code.k:
        print(f"[ERROR] Insufficient chunks for recovery: {collected_chunks} < {erasure_code.k}")
        return jsonify({
            "message": f"Insufficient chunks for recovery: {collected_chunks} < {erasure_code.k}",
            "collected_chunks": collected_chunks,
            "required_chunks": erasure_code.k
        }), 400
    
    # 청크를 리스트로 변환 (chunk_id 순서대로)
    chunk_list = [chunks[i] for i in sorted(chunks.keys())[:erasure_code.k]]
    
    try:
        # 소거 코드 디코딩하여 원본 데이터 복구
        recovered_data = erasure_code.decode(chunk_list)
        recovered_block = json.loads(recovered_data.decode())
        
        # 복구된 블록을 로컬에 저장 (모든 청크 저장)
        for chunk_id, chunk_data in chunks.items():
            storage.save_chunk(chunk_data, LOCAL_IP, block_index, chunk_id=chunk_id)
        
        print(f"[INFO] Successfully recovered block {block_index} from {collected_chunks} chunks")
        return jsonify({
            "message": f"Block {block_index} recovered successfully",
            "collected_chunks": collected_chunks,
            "block": recovered_block
        }), 200
    except Exception as e:
        print(f"[ERROR] Failed to decode recovered chunks: {e}")
        return jsonify({
            "message": f"Failed to decode recovered chunks: {str(e)}",
            "collected_chunks": collected_chunks
        }), 500

# ─── GUI 엔드포인트 ──────────────────────────────────────────

@app.route('/test', methods=['GET'])
def test():
    """테스트 엔드포인트 - 서버가 작동하는지 확인"""
    return jsonify({
        "status": "ok",
        "template_dir": template_dir,
        "static_dir": static_dir,
        "template_exists": os.path.exists(os.path.join(template_dir, 'index.html')),
        "static_exists": os.path.exists(static_dir),
        "current_dir": os.getcwd()
    }), 200

@app.route('/', methods=['GET'])
def index():
    """메인 대시보드 페이지"""
    template_path = os.path.join(template_dir, 'index.html')
    print(f"[DEBUG] Attempting to render template from: {template_path}")
    print(f"[DEBUG] Template file exists: {os.path.exists(template_path)}")
    print(f"[DEBUG] Template directory exists: {os.path.exists(template_dir)}")
    
    try:
        if not os.path.exists(template_path):
            error_msg = f"Template file not found: {template_path}"
            print(f"[ERROR] {error_msg}")
            return f"""
            <html>
            <head><title>Template Not Found</title></head>
            <body>
                <h1>Template Not Found</h1>
                <p>Expected path: {template_path}</p>
                <p>Template directory: {template_dir}</p>
                <p>Current working directory: {os.getcwd()}</p>
                <p>Please check if templates/index.html exists in the project root.</p>
            </body>
            </html>
            """, 404
        
        return render_template('index.html', 
                              local_ip=LOCAL_IP, 
                              local_port=LOCAL_PORT)
    except Exception as e:
        import traceback
        error_trace = traceback.format_exc()
        print(f"[ERROR] Failed to render template: {e}")
        print(f"[ERROR] Traceback: {error_trace}")
        return f"""
        <html>
        <head><title>Template Error</title></head>
        <body>
            <h1>Template Rendering Error</h1>
            <p>Error: {str(e)}</p>
            <p>Template directory: {template_dir}</p>
            <p>Template file exists: {os.path.exists(template_path)}</p>
            <pre>{error_trace}</pre>
        </body>
        </html>
        """, 500

@app.route('/api/status', methods=['GET'])
def api_status():
    """상태 정보 API"""
    return jsonify({
        "local_ip": LOCAL_IP,
        "local_port": LOCAL_PORT,
        "nodes": [f"{ip}:{port}" for ip, port in nodes.items()],
        "chain_length": len(blockchain.chain),
        "pending_transactions": len(blockchain.pending_transactions)
    }), 200

@app.route('/api/chunks', methods=['GET'])
def api_list_chunks():
    """저장된 청크 목록 조회 API"""
    try:
        node_id = request.args.get('node_id', None)
        # node_id가 지정되지 않으면 현재 IP의 청크만 반환
        if node_id is None:
            node_id = LOCAL_IP
        chunks = storage.list_chunks(node_id=node_id)
        return jsonify({
            "chunks": chunks,
            "total": len(chunks),
            "node_id": node_id  # 어떤 노드의 청크인지 반환
        }), 200
    except Exception as e:
        print(f"[ERROR] Failed to list chunks: {e}")
        return jsonify({"message": f"Failed to list chunks: {str(e)}"}), 500

@app.route('/api/chunks/block/<int:block_index>', methods=['GET'])
def api_get_block_chunks(block_index: int):
    """특정 블록의 청크 목록 조회 API"""
    try:
        node_id = request.args.get('node_id', None)
        chunks = storage.get_available_chunks_for_block(block_index, node_id=node_id)
        return jsonify({
            "block_index": block_index,
            "chunks": chunks,
            "total": len(chunks)
        }), 200
    except Exception as e:
        print(f"[ERROR] Failed to get block chunks: {e}")
        return jsonify({"message": f"Failed to get block chunks: {str(e)}"}), 500

@app.route('/api/view_block/<int:block_index>', methods=['GET'])
def api_view_block(block_index: int):
    """
    청크 파일로부터 블록 기록을 열람합니다.
    네트워크에서 청크를 수집하여 원본 블록 데이터를 복구하고 반환합니다.
    """
    # 자신 포함하여 사용 가능한 노드 목록 생성
    available_nodes = [(LOCAL_IP, LOCAL_PORT)] + list(nodes.items())
    
    # n개 청크 수집 시도 (k=2개 이상이면 복구 가능)
    chunks = {}
    collected_chunks = 0
    
    for chunk_id in range(erasure_code.n):
        for node_ip, node_port in available_nodes:
            if chunk_id in chunks:
                break  # 이미 수집한 청크는 건너뛰기
            
            try:
                if node_ip == LOCAL_IP:
                    # 로컬에서 조회
                    if storage.has_chunk(LOCAL_IP, block_index, chunk_id=chunk_id):
                        chunks[chunk_id] = storage.retrieve_chunk(LOCAL_IP, block_index, chunk_id=chunk_id)
                        collected_chunks += 1
                        print(f"[INFO] Collected chunk {chunk_id} from local storage")
                else:
                    # 원격 노드에서 조회
                    r = requests.get(
                        f"http://{node_ip}:{node_port}/get_chunk/{block_index}/{chunk_id}",
                        timeout=30
                    )
                    if r.status_code == 200:
                        chunks[chunk_id] = r.content
                        collected_chunks += 1
                        print(f"[INFO] Collected chunk {chunk_id} from {node_ip}:{node_port}")
                        break
            except Exception as e:
                print(f"[DEBUG] Failed to get chunk {chunk_id} from {node_ip}:{node_port}: {e}")
                continue
    
    # 최소 k개 청크가 수집되었는지 확인
    if collected_chunks < erasure_code.k:
        print(f"[ERROR] Insufficient chunks for viewing: {collected_chunks} < {erasure_code.k}")
        return jsonify({
            "message": f"Insufficient chunks for viewing: {collected_chunks} < {erasure_code.k}",
            "collected_chunks": collected_chunks,
            "required_chunks": erasure_code.k,
            "block_index": block_index
        }), 400
    
    # 청크를 리스트로 변환 (chunk_id 순서대로)
    chunk_list = [chunks[i] for i in sorted(chunks.keys())[:erasure_code.k]]
    
    try:
        # 소거 코드 디코딩하여 원본 데이터 복구
        recovered_data = erasure_code.decode(chunk_list)
        recovered_block = json.loads(recovered_data.decode())
        
        print(f"[INFO] Successfully viewed block {block_index} from {collected_chunks} chunks")
        return jsonify({
            "message": f"Block {block_index} viewed successfully",
            "collected_chunks": collected_chunks,
            "block": recovered_block
        }), 200
    except Exception as e:
        print(f"[ERROR] Failed to decode chunks for viewing: {e}")
        return jsonify({
            "message": f"Failed to decode chunks: {str(e)}",
            "collected_chunks": collected_chunks,
            "block_index": block_index
        }), 500

# ─── 서버 실행 ──────────────────────────────────────────────

if __name__ == '__main__':
    # 등록된 라우트 확인
    print("\n[INFO] Registered routes:")
    for rule in app.url_map.iter_rules():
        print(f"  {rule.rule} -> {rule.endpoint} [{', '.join(rule.methods)}]")
    print()
    
    print(f"[INFO] Starting Flask server on {LOCAL_IP}:{LOCAL_PORT}")
    print(f"[INFO] Access the GUI at: http://localhost:{LOCAL_PORT}/")
    print(f"[INFO] Test endpoint: http://localhost:{LOCAL_PORT}/test\n")
    
    app.run(host='0.0.0.0', port=int(LOCAL_PORT), debug=True)
