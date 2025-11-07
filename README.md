| 기능         | URL 예시                                  | 요청 방식  | 설명                  |
| ---------- | --------------------------------------- | ------ | ------------------- |
| 블록체인 조회  | `http://localhost:5000/get_chain`       | `GET`  | 현재 블록체인 전체 보기       |
| 트랜잭션 추가  | `http://localhost:5000/add_transaction` | `POST` | 새로운 거래 추가           |
| 블록 채굴    | `http://localhost:5000/mine`            | `GET`  | 새 블록 생성 및 체인에 추가    |
| 노드 목록 확인 | `http://localhost:5000/get_nodes`       | `GET`  | 현재 발견된 피어 IP 리스트 출력 |
| 전체 동기화   | `http://localhost:5000/sync_all`        | `GET`  | 다른 노드와 체인 및 청크 동기화  |
| 특정 청크 조회 | `http://localhost:5000/get_chunk/1`     | `GET`  | 블록 1번의 저장된 청크 다운로드  |


| 로그                                     | 설명                             |
| -------------------------------------- | ------------------------------ |
| `[DEBUG] Broadcasting {...}`           | 내가 네트워크에 자신을 알리고 있음            |
| `[DEBUG] Received raw packet from ...` | 다른 노드의 브로드캐스트를 수신함             |
| `[DEBUG] Added peer ...`               | 새 노드 발견 및 등록                   |
| `GET /get_nodes`                       | 다른 노드가 내 `/get_nodes` API를 호출함 |
| `[DEBUG] Block mined...`               | 새로운 블록이 생성되어 체인에 추가됨           |
