import os
import json
import uuid
import random
import numpy as np
import requests
import base64
import time
import uvicorn
import prompts
from slot_process import intent_slot
from function import tools1
from fastapi import FastAPI, Request
from utils import logger
from dm.factory import DMFactory


## 创建FastAPI应用
app = FastAPI()


MAX_CONF = 0.98
TIMEOUT = 5
INTENT_URL = os.environ["INTENT_URL"]
DOUBAO_API_KEY = os.environ["API_KEY"]
DOUBAO_URL = os.environ["BASE_URL"]


id2func = {}
func2name = {}
name2id = {}
with open("../config/class.txt", 'r', encoding='utf-8') as mapfile:
    for line in mapfile:
        id, name, func = line.strip().split(":")
        id2func[id] = func
        func2name[func] = name
        name2id[name] = id

tool_map = {}
with open("../config/slot_intent.json", "r", encoding="utf-8") as slotfile:
    slot_map = json.load(slotfile) #每个意图需要提取哪些槽位的信息
    for item in tools1:
        name = item["function"]["name"]
        if name not in tool_map.keys():
            lst = [item]
            new_dict = {name: lst} #将每个 function 名称 映射到一组 tool definition（用于 LLM 的 function calling）
            tool_map.update(new_dict)
        else:
            tool_map.get(name).append(item)


def send_messages(messages, tool_lst):
    headers = {
        "Authorization": DOUBAO_API_KEY,
        "Content-Type": "application/json"
    }
    data = {
        "model": "ep-20250106153928-kh8t7",
        "messages": messages,
        "tools": tool_lst,
        "temperature": 1e-6,
        "top_p": 0
    }
    try:
        response = requests.post(
            DOUBAO_URL,
            headers=headers,
            data=json.dumps(data),
            timeout=TIMEOUT
        )
        res = response.content.decode('utf-8')
        res = json.loads(res)
        return res['choices'][0]['message']['tool_calls']
    except Exception as e:
        logger.error(f"Doubao error: {e}")
        return None


def intent_recall(query, trace_id):
    headers = {'Content-Type': 'application/json'}
    data = {"query": query, "trace_id": str(uuid.uuid1())}
    response = requests.post(url=INTENT_URL, headers=headers, data=json.dumps(data))
    return response.json()

#先会拿到top-k的意图，
def predict(query, trace_id):
    try:
        start = time.time()
        intent_rec = intent_recall(query, trace_id) #拿到top-k的意图
        results = intent_rec["data"].split(",") #存放前5的函数的id
        max_score = max([float(k) for k in intent_rec["score"].split(",")])
        logger.info(f"top5：{intent_rec['data']}, cost: {time.time() - start}")
        if str(results[0]) == "3" and max_score > MAX_CONF: # 如果top-1是3，且置信度大于阈值，则认为是3
            return "未知-无"

        now_tool = []
        for t in results:
            func = id2func.get(t)
            lst_a = tool_map.get(func)
            if lst_a:
                for s in lst_a:
                    now_tool.append(s)
            else:
                continue
#调用豆包的function——call模型返回相应的结果
        header = [{"role": "system", "content": prompts.NLU_SYSTEM_PROMPT}]
        context = [{"role": "user", "content": query}]
        messages = header + context
        start_time = time.time()
        result = send_messages(messages, now_tool)
        logger.info(f"llm结果：{result}")
        logger.info(f"function调用时间:{time.time() - start_time}")
        if not result:
            return "未知-无"

        nlu = intent_slot(result, func2name, slot_map) #做一个intent的解析，解析大模型通过 Function Calling 返回的结果，将其转换为结构化的 “意图-槽位”字符串格式
    except:
        return "未知-无"

    logger.info(f"返回结果：{nlu}")

    return nlu


@app.post("/chatnlu-server/v1")
async def inference(request: Request):
    json_info = await request.json()

    begin = time.time()
    query = json_info.get("query")
    enable_dm = json_info.get("enable_dm", True)#需不需要做调用mcp
    trace_id = json_info.get("trace_id", "1")

    # 抽取意图和槽位
    nlu = predict(query, trace_id)


    # NLU后处理，有了槽位，有了意图，就可以做一些后处理，看看他是不是规范
    nlu_items = nlu.split("-")
    intent = nlu_items[0]
    if len(nlu_items) > 2:
        slots_str = "-".join(nlu_items[1:])
    else:
        slots_str = nlu_items[1]

    if slots_str != "无":
        slots = {}
        for item in slots_str.split(","):
            if ":" in item:
                if len(item.split(":")) != 2:
                    continue
                k, v = item.split(":")
                slots[k] = v
    else:
        slots = {}
    intent_id = name2id.get(intent)
    func_name = id2func.get(intent_id) 


    response = {
        "query": query,
        "tarce_id": trace_id,
        "intent": intent,
        "intent_id": intent_id,
        "function": func_name,
        "slots": slots,
    }
#如果需要调用mcp，那么就调用mcp
    if enable_dm:
        for name in ["weather", "music", "maps"]:
            dm_result = await DMFactory.get(name)(func_name, query, slots)
            if dm_result:
                tool_response, nlg = dm_result
                response["tool"] = tool_response
                response["nlg"] = nlg

    cost = time.time() - begin
    response["cost"] = cost

    return response

if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8009, workers=1)
