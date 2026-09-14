import os
import requests
import json
import time
import random
import pprint
from time import sleep
# 仅修改导入语句，适配新版python-socketio
import socketio

URL = os.environ["ENTRY_URL"]

# 仅修改客户端实例创建方式，保持新版兼容
sio = socketio.Client()

@sio.on("connect")
def on_connect():
    print("connected to server")

@sio.on("disconnect")
def on_disconnect():
    print("disconnected to server")

@sio.on("message")
def on_message(data):
    print('Received message:', data)

@sio.on("error")
def on_error(e):
    print('Error:', e)

@sio.on("request_nlu")
def on_response(data):
    print('Response:', end="")
    data = json.loads(data)
    print(data)


def rand_str(size=6):
    return "".join(random.sample("1234567890zyxwvutsrqponmlkjihgfedcba", size))


if __name__ == "__main__":

    data = {
        "sender_id": rand_str(9)
    }

    sio.connect(URL)

    while True:
        data["trace_id"] = rand_str(9)
        print("enter query: ")
        query = input().strip()
        data["query"] = query
        data["enable_dm"] = True
        sio.emit("request_nlu", json.dumps(data, ensure_ascii=False))

    print("done")

