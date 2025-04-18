from reedsolo import RSCodec

class ErasureCode:
    def __init__(self, k: int = 4, n: int = 6):
        self.k = k  # 데이터 조각 수
        self.n = n  # 총 조각 수 (데이터 + 패리티)
        self.rsc = RSCodec(n - k)

    def encode(self, data: bytes, k: int = None, n: int = None):
        k = k or self.k
        n = n or self.n
        return self.rsc.encode(data)

    def decode(self, chunks: bytes):
        return self.rsc.decode(chunks)[0]
