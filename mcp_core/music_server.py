# -*- coding: utf-8 -*-

import asyncio
from qqmusic_api import search
from mcp.server.fastmcp import FastMCP
import json

# Initialize FastMCP server
mcp = FastMCP("mcp-qqmusic-test-server")


@mcp.tool() #表示这个函数是一个可通过 MCP 协议调用的“工具”
async def search_music(keyword: str, page: int = 1, num: int = 3):
    """
    Search for music tracks
    
    Args:
        keyword: Search keyword or phrase
        page: Page number for pagination (default: 1)
        num: Maximum number of results to return (default: 20)
        
    Returns:
        List of music tracks matching the search criteria
    """
    result = await search.search_by_type(keyword=keyword, page=page, num=num)
    
    # 提取指定字段
    if isinstance(result, list):
        filtered_list = []
        for item in result:
            # 提取歌曲信息而不是专辑信息
            song_info = {
                "id": item.get("id"), #歌曲数字 ID
                "mid": item.get("mid"), #歌曲唯一标识符（常用于 QQ 音乐 URL）
                "name": item.get("name"),
                "pmid": item.get("pmid", ""),
                "icon_url": item.get("icon_url", ""),
                "subtitle": item.get("subtitle", ""),
                "time_public": item.get("time_public", ""), #发行时间
                "title": item.get("title", item.get("name", ""))
            }
            filtered_list.append(song_info)
    
    return filtered_list


if __name__ == "__main__":
    #res = asyncio.run(search_music("周杰伦 七里香"))
    #for item in res:
    #    print(item)
    mcp.run(transport='stdio')

