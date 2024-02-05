import json

from websocket_server import WebsocketServer

# THIS IS CURRENTLY VERY WIP!!!

WSHOST = "localhost"
WSPORT = 8765

global c,s

def send(server: WebsocketServer, data):
	server.send_message_to_all(json.dumps(data))
	
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