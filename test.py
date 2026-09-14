import os
import requests
import json
import time
import random
import pprint
import socketio
import queue
from time import sleep

URL = os.environ["ENTRY_URL"]

sio = socketio.Client()
data_q = queue.Queue(2000) #存服务器响应


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
    data_q.put(data)#放入主线程处理
    print(data)

#是随机生成用户id
def rand_str(size=6):
    return "".join(random.sample("1234567890zyxwvutsrqponmlkjihgfedcba", size))


if __name__ == "__main__":

    fd = open("test/data/multi_test.txt")
    fw = open("test/result/multi_test_output.txt", "w")
    for line in fd:
        # 连接到服务器（每个会话重新连接）
        sio.connect(URL)
        data = {
            "sender_id": rand_str(9)
        }
        sessions = [t.strip() for t in line.split("\t") if t.strip()]
        for query in sessions:
            data["trace_id"] = rand_str(9)
            data["query"] = query
            data["enable_dm"] = False
            # 发送请求到服务器
            sio.emit("request_nlu", json.dumps(data, ensure_ascii=False))
            #结果容器
            result = {}
            result["query"] = query
            result["res"] = []

            while not data_q.empty():
                while True:
                    response = data_q.get()
                    result["res"].append(response)
                    #技能型一次性返回，先聊性实时返回，先聊性结束状态码是2
                    if response.get("intent") != "闲聊百科" or response.get("intent") == "闲聊百科" and response.get("status") == 2:
                        break
                break

            result_str = json.dumps(result, ensure_ascii=False)
            fw.write(result_str + "\n")
            fw.flush()
        sio.disconnect()

    print("done")

