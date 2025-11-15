"""Simple CLI chatbot that talks to the Crypto Market MCP server.

This CLI connects to the MCP server over stdio using the MCP wire protocol,
demonstrating how to call tools via ClientSession.
"""
from __future__ import annotations

import asyncio
from typing import Any, Dict

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def _chat_loop() -> None:
    print("Crypto Market Chatbot. Ask things like 'price BTC/USDT' or 'ohlcv BTC/USDT'. Type 'quit' to exit.")

    params = StdioServerParameters(command="crypto-market-mcp")

    async with stdio_client(params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize the session
            await session.initialize()
            
            print("Connected to MCP server. Type 'price SYMBOL' or 'ohlcv SYMBOL', or 'quit' to exit.")

            while True:
                user_input = input("you> ").strip()
                if user_input.lower() in {"quit", "exit"}:
                    break

                try:
                    if user_input.startswith("price "):
                        symbol = user_input.split(" ", 1)[1]
                        result = await session.call_tool("get_ticker", arguments={"symbol": symbol})
                    elif user_input.startswith("ohlcv "):
                        symbol = user_input.split(" ", 1)[1]
                        result = await session.call_tool("get_ohlcv", arguments={"symbol": symbol, "limit": 10})
                    else:
                        print("Unknown command. Use 'price SYMBOL' or 'ohlcv SYMBOL'.")
                        continue

                    # Extract the content from the MCP response
                    if hasattr(result, 'content') and result.content:
                        for content_item in result.content:
                            if hasattr(content_item, 'text'):
                                print("mcp>", content_item.text)
                            else:
                                print("mcp>", content_item)
                    else:
                        print("mcp>", result)
                except Exception as exc:  # pragma: no cover - for demo convenience
                    print("Error talking to MCP server:", exc)


def main() -> None:
    asyncio.run(_chat_loop())


if __name__ == "__main__":  # pragma: no cover
    main()
