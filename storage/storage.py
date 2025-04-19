import os

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
