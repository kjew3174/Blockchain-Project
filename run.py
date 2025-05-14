from network.node import app
from storage.storage import Storage
from blockchain.blockchain import Blockchain
from blockchain.transaction import Transaction
import threading
import time

# 초기화
storage = Storage()
blockchain = Blockchain()

# 테스트 데이터 추가 (옵션)
def add_test_data():
    transaction1 = Transaction("Alice", "Bob", 10.0)
    transaction2 = Transaction("Bob", "Charlie", 5.0)

    blockchain.pending_transactions.append(transaction1.to_dict())
    blockchain.pending_transactions.append(transaction2.to_dict())

    print("[INFO] Test transactions added")

# 노드 서버 실행
def run_server():
    app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    # 테스트 데이터 추가
    add_test_data()

    # 서버 실행
    server_thread = threading.Thread(target=run_server)
    server_thread.start()

    print("[INFO] Node server running at http://localhost:5000")
