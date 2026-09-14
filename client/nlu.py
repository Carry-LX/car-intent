# -*- coding: utf-8 -*-
"""
自然语言理解(NLU)客户端模块

本模块通过HTTP请求与远程NLU服务通信，实现对用户输入文本的自然语言理解。
具体功能：
  1. 将用户的自然语言查询发送到NLU模型服务
  2. 从用户输入中提取用户意图(Intent)和关键信息(槽位/Slot)
  3. 返回结构化的NLU识别结果，供后续对话管理和任务执行使用

工作流程：
  用户输入 -> 构建请求 -> 调用远程NLU服务 -> 解析意图和槽位 -> 返回结构化结果
"""

import json
import requests
import re
import os
from utils import logger
from typing import List


NLU_URL = os.environ["NLU_URL"]


def request_nlu(query, trace_id, enable_dm=True):
    """
    调用远程NLU服务识别用户意图和槽位信息
    
    通过HTTP POST请求将用户的自然语言查询发送到NLU模型，获取结构化的意图识别结果。
    NLU模型会从用户输入中提取：
      - 用户意图(Intent)：用户想要做什么
      - 槽位信息(Slots)：意图相关的关键参数和属性
    
    参数:
        query (str): 用户的自然语言输入文本
        trace_id (str): 请求的追踪ID，用于日志追踪和调试
        enable_dm (bool): 是否启用对话管理模块，默认为True
    
    返回:
        dict: NLU模型的识别结果，包含意图、槽位等结构化信息
              如果请求失败则返回空字典 {}
    """
    headers = {
        "Content-Type":"application/json"
    }
    payload = json.dumps({
        "query": query,
        "trace_id": trace_id,
        "enable_dm": enable_dm
    })
    try:
        response = requests.post(
            NLU_URL,
            headers=headers,
            data=payload
        )
        res = response.json()
        logger.info(f"NLU模型的输出：{res}")
    except Exception as e:
        logger.error(f"call NLU failed:{e}")
        res = {}
    return res


if __name__ == '__main__':
    while True:
        query = input("Input:")
        res = request_nlu(query, "123")
        print(res)

