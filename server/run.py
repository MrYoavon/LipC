# run.py
import asyncio
from websockets import serve
from utils.connection import handle_connection


def main():
    print("Starting WebSocket server...")
    server_host = "192.168.1.5"  # Update as needed.
    server_port = 8765
    asyncio.run(start_server(server_host, server_port))


async def start_server(host, port):
    async with serve(handle_connection, host, port):
        print(f"WebSocket server started on ws://{host}:{port}")
        await asyncio.Future()  # Run forever


if __name__ == "__main__":
    main()
