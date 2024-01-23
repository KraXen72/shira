
from sys import argv

from .cli import cli
from .server import server

# print(argv)
if argv[1] == "server" or argv[1] == "server.py":
	server()
else:
	cli()

