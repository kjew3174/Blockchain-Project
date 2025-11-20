import os
import json

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
    
    def list_chunks(self, node_id: str = None) -> list[dict]:
        """
        저장된 청크 목록을 조회합니다.
        :param node_id: 특정 노드 ID로 필터링 (None이면 모든 노드)
        :return: 청크 정보 리스트 [{"node_id": str, "block_index": int, "chunk_id": int}, ...]
        """
        chunks = []
        
        if node_id:
            # 특정 노드의 청크만 조회
            node_folder = os.path.join(self.base_path, node_id)
            if os.path.exists(node_folder):
                for filename in os.listdir(node_folder):
                    if filename.startswith("chunk_") and filename.endswith(".bin"):
                        # chunk_{block_index}_{chunk_id}.bin 형식 파싱
                        try:
                            parts = filename.replace("chunk_", "").replace(".bin", "").split("_")
                            block_index = int(parts[0])
                            chunk_id = int(parts[1]) if len(parts) > 1 else 0
                            chunks.append({
                                "node_id": node_id,
                                "block_index": block_index,
                                "chunk_id": chunk_id
                            })
                        except (ValueError, IndexError):
                            continue
        else:
            # 모든 노드의 청크 조회
            if os.path.exists(self.base_path):
                for node_folder_name in os.listdir(self.base_path):
                    node_folder = os.path.join(self.base_path, node_folder_name)
                    if os.path.isdir(node_folder):
                        for filename in os.listdir(node_folder):
                            if filename.startswith("chunk_") and filename.endswith(".bin"):
                                try:
                                    parts = filename.replace("chunk_", "").replace(".bin", "").split("_")
                                    block_index = int(parts[0])
                                    chunk_id = int(parts[1]) if len(parts) > 1 else 0
                                    chunks.append({
                                        "node_id": node_folder_name,
                                        "block_index": block_index,
                                        "chunk_id": chunk_id
                                    })
                                except (ValueError, IndexError):
                                    continue
        
        # block_index, chunk_id 순으로 정렬
        chunks.sort(key=lambda x: (x["block_index"], x["chunk_id"]))
        return chunks
    
    def get_available_chunks_for_block(self, block_index: int, node_id: str = None) -> list[dict]:
        """
        특정 블록에 대한 사용 가능한 청크 목록을 조회합니다.
        :param block_index: 블록 인덱스
        :param node_id: 특정 노드 ID로 필터링 (None이면 모든 노드)
        :return: 청크 정보 리스트
        """
        all_chunks = self.list_chunks(node_id)
        return [chunk for chunk in all_chunks if chunk["block_index"] == block_index]
    
    def save_block_metadata(self, node_id: str, block_index: int, metadata: dict) -> None:
        """
        블록의 메타데이터(해시, 타임스탬프, nonce)를 저장합니다.
        :param node_id: 노드 ID (IP 주소)
        :param block_index: 블록 인덱스
        :param metadata: 메타데이터 딕셔너리 {"hash": str, "timestamp": float, "nonce": int, "previous_hash": str}
        """
        node_folder = os.path.join(self.base_path, node_id)
        os.makedirs(node_folder, exist_ok=True)
        metadata_path = os.path.join(node_folder, f"metadata_{block_index}.json")
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2)
    
    def get_block_metadata(self, node_id: str, block_index: int) -> dict | None:
        """
        블록의 메타데이터를 조회합니다.
        :param node_id: 노드 ID (IP 주소)
        :param block_index: 블록 인덱스
        :return: 메타데이터 딕셔너리 또는 None
        """
        metadata_path = os.path.join(self.base_path, node_id, f"metadata_{block_index}.json")
        if not os.path.exists(metadata_path):
            return None
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARN] Failed to read metadata for block {block_index}: {e}")
            return None
    
    def has_block_metadata(self, node_id: str, block_index: int) -> bool:
        """
        블록 메타데이터가 존재하는지 확인합니다.
        :param node_id: 노드 ID (IP 주소)
        :param block_index: 블록 인덱스
        :return: 메타데이터 존재 여부
        """
        metadata_path = os.path.join(self.base_path, node_id, f"metadata_{block_index}.json")
        return os.path.exists(metadata_path)