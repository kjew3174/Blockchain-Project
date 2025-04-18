import requests
from blockchain.blockchain import Blockchain

class Sync:
    def sync_chain(self, blockchain: Blockchain, target_node: str):
        try:
            response = requests.get(f"http://{target_node}/get_chain")
            if response.status_code == 200:
                remote_chain = response.json().get("chain", [])
                if len(remote_chain) > len(blockchain.chain):
                    blockchain.replace_chain(remote_chain)
                    return True
        except Exception as e:
            print(f"[ERROR] Sync failed: {e}")
        return False

    def sync_storage(self, node_id: str):
        # 추후 구현 예정 (소거 코드 연동)
        pass