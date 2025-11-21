from reedsolo import RSCodec
import math

class ErasureCode:
    def __init__(self, k: int = 2, n: int = 3):
        self.k = k  # 데이터 조각 수
        self.n = n  # 총 조각 수 (데이터 + 패리티)
        self.rsc = RSCodec(n - k)

    def encode(self, data: bytes, k: int | None = None, n: int | None = None) -> list[bytes]:
        """
        데이터를 소거 코드로 인코딩하여 n개의 청크로 분할합니다.
        :param data: 인코딩할 데이터
        :param k: 데이터 조각 수 (기본값: self.k)
        :param n: 총 조각 수 (기본값: self.n)
        :return: n개의 청크 리스트
        """
        k = k or self.k
        n = n or self.n
        
        # 데이터를 k개로 분할
        data_len = len(data)
        chunk_size = math.ceil(data_len / k)
        
        # k개 청크로 분할 (마지막 청크는 패딩)
        chunks = []
        for i in range(k):
            start = i * chunk_size
            end = min((i + 1) * chunk_size, data_len)
            chunk = data[start:end]
            # 패딩 추가 (마지막 청크가 작을 경우)
            if len(chunk) < chunk_size:
                chunk += b'\x00' * (chunk_size - len(chunk))
            chunks.append(chunk)
        
        # 각 청크에 대해 패리티 계산
        parity_chunks = []
        for i in range(n - k):
            # 각 청크의 같은 위치 바이트에 대해 패리티 계산
            parity_chunk = bytearray()
            for pos in range(chunk_size):
                bytes_to_encode = bytes([chunks[j][pos] for j in range(k)])
                encoded = self.rsc.encode(bytes_to_encode)
                # 패리티 바이트만 추출 (원본 k바이트 제외)
                parity_byte = encoded[k + i] if len(encoded) > k + i else 0
                parity_chunk.append(parity_byte)
            parity_chunks.append(bytes(parity_chunk))
        
        # 데이터 청크 + 패리티 청크 반환
        return chunks + parity_chunks

    def decode(self, chunks: list[bytes]) -> bytes:
        """
        n개 청크 중 k개 이상을 사용하여 원본 데이터를 복구합니다.
        :param chunks: 청크 리스트 (최소 k개 필요, 최대 n개)
        :return: 복구된 원본 데이터
        """
        if len(chunks) < self.k:
            raise ValueError(f"Need at least {self.k} chunks to decode, got {len(chunks)}")
        
        # 모든 청크의 크기가 같은지 확인
        chunk_size = len(chunks[0])
        for chunk in chunks:
            if len(chunk) != chunk_size:
                raise ValueError(f"All chunks must have the same size. Expected {chunk_size}, got {len(chunk)}")
        
        # 각 위치별로 디코딩
        decoded_data = bytearray()
        for pos in range(chunk_size):
            # 각 청크의 해당 위치에서 바이트 수집
            bytes_at_pos = []
            for chunk in chunks:
                if pos < len(chunk):
                    bytes_at_pos.append(chunk[pos])
            
            # 최소 k개 바이트가 필요
            if len(bytes_at_pos) < self.k:
                raise ValueError(f"Need at least {self.k} bytes at position {pos}, got {len(bytes_at_pos)}")
            
            # k개 이상의 바이트가 있으면 디코딩 시도
            # RSCodec는 k + (n-k) = n개 바이트를 기대하므로, n개 바이트를 준비
            bytes_to_decode = bytes(bytes_at_pos[:self.n]) if len(bytes_at_pos) >= self.n else bytes(bytes_at_pos[:self.k])
            
            try:
                # RSCodec.decode()는 인코딩된 전체 바이트 배열을 받아서 디코딩
                # encode에서 k개 바이트를 인코딩하여 n개 바이트를 생성했으므로,
                # decode에서는 n개 바이트가 필요함
                if len(bytes_to_decode) < self.n:
                    # n개 미만이면 패딩 추가 (손상된 경우)
                    bytes_to_decode = bytes_to_decode + bytes([0] * (self.n - len(bytes_to_decode)))
                
                decoded = self.rsc.decode(bytes_to_decode)
                # 디코딩 결과는 원본 k개 바이트
                decoded_data.append(decoded[0] if len(decoded) > 0 else bytes_to_decode[0])
            except Exception as e:
                # 디코딩 실패 시 첫 번째 바이트 사용 (손상된 데이터)
                print(f"[WARN] Failed to decode at position {pos}: {e}, using first byte")
                decoded_data.append(bytes_to_decode[0] if len(bytes_to_decode) > 0 else 0)
        
        # 패딩 제거 (마지막의 0 바이트들)
        while len(decoded_data) > 0 and decoded_data[-1] == 0:
            decoded_data.pop()
        
        return bytes(decoded_data)
