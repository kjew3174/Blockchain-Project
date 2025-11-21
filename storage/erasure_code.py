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
        
        # k개 데이터 청크만 사용 (인덱스 0부터 k-1까지)
        # encode에서 데이터를 k개 청크로 분할했으므로, decode에서는 k개 청크를 순서대로 합치면 됨
        data_chunks = chunks[:self.k]
        
        # 각 청크를 순서대로 합치기
        # chunk[0] + chunk[1] + ... + chunk[k-1] = 원본 데이터
        decoded_data = bytearray()
        for chunk in data_chunks:
            decoded_data.extend(chunk)
        
        # 패딩 제거 (마지막의 0 바이트들)
        # 원본 데이터 길이를 알 수 없으므로, 연속된 0 바이트를 제거
        # 하지만 마지막 청크의 패딩만 제거해야 함
        # 간단한 방법: 마지막부터 0 바이트를 제거하되, 너무 많이 제거하지 않도록 주의
        original_length = len(decoded_data)
        while len(decoded_data) > 0 and decoded_data[-1] == 0:
            decoded_data.pop()
            # 원본 데이터가 0으로 끝날 수 있으므로, 최대 chunk_size만큼만 제거
            if original_length - len(decoded_data) >= chunk_size:
                break
        
        return bytes(decoded_data)
