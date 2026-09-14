import os
import json
import re
import time
import requests
import prompts
from utils import logger
from utils.redis_tool import RedisClient


MAX_HIS = 6
TTL = 45
REMIND_TIMEOUT = 2.5# 提醒超时时间（未使用）
REDIS_KEY = "voice:chat_history:{}"
_redis_client = RedisClient() 


DOUBAO_API_KEY = os.environ["API_KEY"]
DOUBAO_BOT_URL = os.environ["BOT_URL"]
SYSTEM_PROMPT = prompts.BOT_CHAT_SYSTEM_PROMPT


def request_chat(query, sender_id, multiturn=True):
    if multiturn:
        history = _redis_client.get(REDIS_KEY.format(sender_id))
        if history:
            history = json.loads(history)
        else:
            history = []
    else:
        history = []
    headers = {
        "Authorization": DOUBAO_API_KEY, 
        "Content-Type": "application/json"
    }
    messages_header = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]
    messages_now = [
        {"role": "user", "content": query}
    ]
    messages = messages_header + history + messages_now
    logger.info(f'request message:{messages}')
    data = {
        "model": "bot-20250227131955-snjfg",
        "messages": messages,
        "stream": True
    }
    try:
        response = requests.post(
            DOUBAO_BOT_URL,
            headers=headers,
            data=json.dumps(data),
            stream=True  # 保持连接，流式读取
        )
        return response
    except Exception as e:
        logger.error("Bot Chat error:" + str(e))
        return "N"


def process_chat(response, query, sender_id):
    if response is None:
        response = "抱歉，此为敏感信息，请您换个问题"
        yield response
    if response == "N":
        response = "抱歉，网络有点问题，请您再试一下"
        yield response
    else:
        counter = 1  # 计数器，用于控制分帧
        uttrance = ""  # 当前帧的累积文本
        answer = ""  # 完整的回答
        # 逐行读取流式响应
        for r in response.iter_lines(chunk_size=1, decode_unicode=False, delimiter=b'\n'):
            r = r.decode("utf-8").strip()
            if not r:
                continue
            r = json.loads(r.lstrip("data: ")) # 解析JSON数据（豆包API返回格式：data: {...}）
            if r["choices"][0].get("finish_reason", {}) == "stop":
                break
            text = r["choices"][0]["delta"]["content"]
            uttrance += text
            answer += text
            # 3. 分帧逻辑（关键！）
            # 规则1：遇到中文标点（，。？；）时返回一帧
            if re.search('，|。|？|；', text):
                yield uttrance
                uttrance = ""
                counter = 1
            # 规则2：每累积5个字符返回一帧
            if counter % 5 == 0:
                yield uttrance
                uttrance = ""
            counter += 1

        if uttrance and uttrance != "  " and uttrance != " ":
            yield uttrance

        logger.info(f"bot_Chat Result: {answer}")
         # 6. 保存对话历史到Redis
        history = _redis_client.get(REDIS_KEY.format(sender_id))
        if history:
            history = json.loads(history)
        else:
            history = []
        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": answer})
        # 保持最近MAX_HIS轮对话
        history = history[-MAX_HIS:]
        history_str = json.dumps(history, ensure_ascii=False)
        # 保存到Redis，45秒后过期
        _redis_client.set(REDIS_KEY.format(sender_id), history_str, ex=TTL)


if __name__ == '__main__':
    while 1:
        query = input("-->")
        res = request_doubao_bot(query, '1', '2')
        for frame in process_chat_bot(res, query, '1', time.time()):
            print(frame)

