import os

class Storage:
    def __init__(self, base_path: str = "./chunks"):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    def save_chunk(self, chunk: bytes, node_id: str, block_index: int, chunk_id: int = 0) -> None:
        """
        청크를 저장합니다.
        :param chunk: 저장할 청크 데이터
        :param node_id: 노드 ID (IP 주소)
        :param block_index: 블록 인덱스
        :param chunk_id: 청크 ID (0~n-1, 기본값 0)
        """
        node_folder = os.path.join(self.base_path, node_id)
        os.makedirs(node_folder, exist_ok=True)
        file_path = os.path.join(node_folder, f"chunk_{block_index}_{chunk_id}.bin")
        with open(file_path, "wb") as f:
            f.write(chunk)

    def retrieve_chunk(self, node_id: str, block_index: int, chunk_id: int = 0) -> bytes:
        """
        청크를 조회합니다.
        :param node_id: 노드 ID (IP 주소)
        :param block_index: 블록 인덱스
        :param chunk_id: 청크 ID (0~n-1, 기본값 0)
        :return: 청크 데이터
        """
        file_path = os.path.join(self.base_path, node_id, f"chunk_{block_index}_{chunk_id}.bin")
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Chunk not found: {file_path}")
        with open(file_path, "rb") as f:
            return f.read()
    
    def has_chunk(self, node_id: str, block_index: int, chunk_id: int = 0) -> bool:
        """
        청크가 존재하는지 확인합니다.
        :param node_id: 노드 ID (IP 주소)
        :param block_index: 블록 인덱스
        :param chunk_id: 청크 ID (0~n-1, 기본값 0)
        :return: 청크 존재 여부
        """
        file_path = os.path.join(self.base_path, node_id, f"chunk_{block_index}_{chunk_id}.bin")
        return os.path.exists(file_path)
