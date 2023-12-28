# a websocket server that has a "publish" method, when called it
# will send the data in json, to all connected clients
import asyncio

import requests
import websockets


class WebsocketServer:
    def __init__(self, port=6542):
        self.port = port
        self.clients = set()
        self.loop = asyncio.get_event_loop()
        self.server = None
        self.running = False
        # get public ip
        self.ip = requests.get("https://checkip.amazonaws.com").text.strip()
        self.last_worker_data = None
        self.last_status_data = None

    async def publish(self, data, type="worker"):
        if type == "worker":
            self.last_worker_data = data
        elif type == "status":
            self.last_status_data = data
        for client in self.clients:
            await client.send(data)

    async def handler(self, websocket):
        self.clients.add(websocket)
        # tqdm.write(f"New client connected, total clients: {len(self.clients)}")
        try:
            async for message in websocket:
                if message == "worker":
                    await websocket.send(self.last_worker_data)
                elif message == "status":
                    await websocket.send(self.last_status_data)
        finally:
            # print("Client disconnected")
            self.clients.remove(websocket)

    async def start(self):
        self.running = True
        self.server = await websockets.serve(
            self.handler, host="0.0.0.0", port=self.port
        )
        await self.server.wait_closed()

    def run(self):
        self.ws_task = self.loop.create_task(self.start())

    def stop(self):
        self.server.close()
        self.ws_task.cancel()
        self.running = False
        self.loop.close()
