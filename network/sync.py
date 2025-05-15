import requests
from blockchain.blockchain import Blockchain
from storage.storage import Storage
from storage.erasure_code import ErasureCode

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
