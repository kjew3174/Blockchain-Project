import requests

class Client:
    def __init__(self, node_address: str):
        self.node_address = node_address

    def send_transaction(self, sender: str, receiver: str, amount: float):
        data = {
            "sender": sender,
            "receiver": receiver,
            "amount": amount
        }
        response = requests.post(f"http://{self.node_address}/add_transaction", json=data)
        return response.json()

    def get_blockchain(self):
        response = requests.get(f"http://{self.node_address}/get_chain")
        return response.json()
