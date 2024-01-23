# import datetime
import json

from websocket_server import WebsocketServer

WSHOST = "localhost"
WSPORT = 8765

global c,s

def send(server: WebsocketServer, data):
	server.send_message_to_all(json.dumps(data))

# async def send_heartbeat():
# 	while True:
# 		send(s, datetime.datetime.utcnow().isoformat())
# 		await asyncio.sleep(3)

# async def capture_incoming():
# 	while True:
# 		data = c.recv(WSPORT)
# 		if data:
# 			print(data)
# 			data = ""
	

# async def new_client(client, server: WebsocketServer):
# 	print("client connected", client["id"])
# 	global c
# 	global s
# 	c = client
# 	s = server
# 	while True:
# 		await asyncio.gather(send_heartbeat(), capture_incoming())
	
def message_received(client, server, message):
    if len(message) > 200:
        message = message[:200]+"..."
    print(f"Client({client["id"]}) said: {message}")
	
def nclient(client, server: WebsocketServer):
	print("new client joined:", client["id"])
	send(server, json.dumps(f"hello from server! you are client {client["id"]}"))

def lclient(client, server: WebsocketServer):
	print(f"client {client["id"]} disconnected")
		

def server():
	server = WebsocketServer(host=WSHOST, port=WSPORT)
	print(f"created websocket server on ws://{WSHOST}:{WSPORT}")
	print("waiting for atleast one client")

	server.set_fn_new_client(nclient)
	server.set_fn_client_left(lclient)
	server.set_fn_message_received(message_received)
	server.run_forever()