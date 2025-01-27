import asyncio
from app.websocket_server import start_server

def main():
    print("Starting WebSocket server...")
    asyncio.run(start_server())

if __name__ == "__main__":
    main()
