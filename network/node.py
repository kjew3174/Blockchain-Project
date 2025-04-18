from flask import Flask, request, jsonify
from blockchain.blockchain import Blockchain
from blockchain.transaction import Transaction

app = Flask(__name__)
blockchain: Blockchain = Blockchain()
nodes: set[str] = set()  # 네트워크에 연결된 노드들의 주소 목록

@app.route('/register_node', methods=['POST'])
def register_node() -> tuple[dict, int]:
    """
    새로운 노드를 네트워크에 등록하는 API 엔드포인트.
    요청 데이터 예시: {"node_address": "http://192.168.1.2:5000"}
    """
    data: dict = request.get_json()
    node_address: str = data.get("node_address")
    
    if not node_address:
        return jsonify({"message": "Invalid node address"}), 400

    nodes.add(node_address)
    return jsonify({"message": "Node registered successfully", "nodes": list(nodes)}), 201

@app.route('/add_transaction', methods=['POST'])
def add_transaction() -> tuple[dict, int]:
    """
    새로운 트랜잭션을 추가하는 API 엔드포인트.
    요청 데이터 예시: {"sender": "Alice", "receiver": "Bob", "amount": 10.5}
    """
    data: dict = request.get_json()
    sender: str = data.get("sender")
    receiver: str = data.get("receiver")
    amount: float = data.get("amount")

    if not sender or not receiver or amount is None:
        return jsonify({"message": "Invalid transaction data"}), 400

    transaction: Transaction = Transaction(sender, receiver, amount)
    blockchain.pending_transactions.append(transaction)

    return jsonify({"message": "Transaction added successfully"}), 201

@app.route('/mine', methods=['GET'])
def mine() -> tuple[dict, int]:
    """
    새로운 블록을 채굴하고 블록체인에 추가하는 API 엔드포인트.
    """
    last_block = blockchain.get_latest_block()
    new_block = blockchain.create_new_block()

    blockchain.add_block(new_block)

    return jsonify({"message": "New block mined", "block": new_block.to_dict()}), 200

@app.route('/get_chain', methods=['GET'])
def get_chain() -> tuple[dict, int]:
    """
    현재 블록체인을 반환하는 API 엔드포인트.
    """
    chain_data: list[dict] = [block.to_dict() for block in blockchain.chain]
    return jsonify({"length": len(chain_data), "chain": chain_data}), 200

@app.route('/sync', methods=['GET'])
def sync() -> tuple[dict, int]:
    """
    네트워크에 연결된 모든 노드와 블록체인을 동기화하는 API 엔드포인트.
    """
    global blockchain
    longest_chain: list[dict] = blockchain.chain
    max_length: int = len(longest_chain)

    for node in nodes:
        response = requests.get(f"{node}/get_chain")
        if response.status_code == 200:
            node_chain: list[dict] = response.json()["chain"]
            node_length: int = len(node_chain)

            if node_length > max_length:
                longest_chain = node_chain
                max_length = node_length

    if longest_chain != blockchain.chain:
        blockchain.replace_chain(longest_chain)

    return jsonify({"message": "Blockchain synchronized"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
