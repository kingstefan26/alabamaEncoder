import asyncio
import json
import os
import socket
import time

import psutil
import requests
import websockets
from tqdm import tqdm


class WebsiteUpdate:

    def __init__(self, ctx):
        self.ctx = ctx
        self.current_step_callback = None
        self.proc_done_callback = None
        self.proc_done = 0
        self.current_step_name = "idle"
        self.last_update = None
        self.update_proc_throttle = 0
        self.update_max_freq_sec = 1600
        self.ws_server = None

    async def update_website(self):
        api_url = os.environ.get("status_update_api_url", "")
        token = os.environ.get("status_update_api_token", "")
        if api_url != "":
            if token == "":
                print("Url is set, but token is not, not updating status api")
                return

            should_update_api = False

            if time.time() - self.update_proc_throttle > self.update_max_freq_sec:
                self.update_proc_throttle = time.time()
                should_update_api = True

            #         curl -X POST -d '{"action":"update","data":{"img":"https://domain.com/poster.avif","status":100,
            #         "title":"Show 2024 E01S01","phase":"Done"}}'
            #         -H 'Authorization: Bearer token' 'https://domain.com/update'

            status_data = {
                "action": "update",
                "data": {
                    "img": self.ctx.poster_url,
                    "status": round(self.proc_done, 1),  # rounded
                    "title": self.ctx.get_title(),
                    "phase": self.current_step_name,
                },
            }

            if self.last_update == status_data:
                return

            self.last_update = status_data

            if should_update_api:
                try:
                    requests.post(
                        api_url + "/statuses/update",
                        json=status_data,
                        headers={"Authorization": f"Bearer {token}"},
                    )
                except Exception as e:
                    self.ctx.log(f"Failed to update status api: {e}")

                self.ctx.log("Updated encode status api")

            #  curl -X POST -d '{"action":"update","data":{"id":"kokoniara-B550MH",
            #  "status":"working on title", "utilization":95}}' -H 'Authorization: Bearer token'
            #  'http://domain.com/workers/update'

            worker_data = {
                "action": "update",
                "data": {
                    "id": (socket.gethostname()),
                    "status": f"Working on {self.ctx.get_title()}",
                    "utilization": int(psutil.cpu_percent()),
                    "ws_ip": self.ws_server.ip if self.ws_server is not None else "",
                },
            }

            if should_update_api:
                try:
                    requests.post(
                        api_url + "/workers/update",
                        json=worker_data,
                        headers={"Authorization": f"Bearer {token}"},
                    )
                except Exception as e:
                    self.ctx.log(f"Failed to worker update status api: {e}")

                self.ctx.log("Updated worker status api")

    def update_current_step_name(self, step_name):
        self.current_step_name = step_name
        if self.current_step_callback is not None:
            self.current_step_callback(step_name)

        asyncio.create_task(self.update_website())

    def update_proc_done(self, proc_done):
        self.proc_done = proc_done
        if self.proc_done_callback is not None:
            self.proc_done_callback(proc_done)

        # update max every minute the proc done
        asyncio.create_task(self.update_website())

    async def constant_updates(self):
        if (
            os.environ.get("status_update_api_url", "") == ""
            or os.environ.get("ws_update", "false") == "false"
        ):
            return

        tqdm.write("Starting constant updates")
        self.ws_server = WebsocketServer()
        self.ws_server.run()
        while True:
            worker_data = {
                "type": "worker",
                "data": {
                    "id": (socket.gethostname()),
                    "status": f"Working on {self.ctx.get_title()}",
                    "utilization": int(psutil.cpu_percent()),
                    "ws_ip": self.ws_server.ip if self.ws_server is not None else "",
                },
            }
            status_data = {
                "type": "status",
                "data": {
                    "img": self.ctx.poster_url,
                    "status": round(self.proc_done, 1),  # rounded
                    "title": self.ctx.get_title(),
                    "phase": self.current_step_name,
                },
            }

            await self.ws_server.publish(json.dumps(worker_data), type="worker")
            await self.ws_server.publish(json.dumps(status_data), type="status")
            await asyncio.sleep(0.5)


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
