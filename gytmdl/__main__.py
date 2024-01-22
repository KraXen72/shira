from websocket_server import WebsocketServer

from .cli import runtime

WSHOST = "localhost"
WSPORT = 8765

server = WebsocketServer(host=WSHOST, port=WSPORT)
print(f"created websocket server on ws://{WSHOST}:{WSPORT}")
print("waiting for atleast one client")

def new_client(client, server):
	runtime(wsserver=server)

server.set_fn_new_client(new_client)
server.run_forever()

