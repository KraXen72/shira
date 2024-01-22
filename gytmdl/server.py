import logging
from typing import Literal

LogPurpose = Literal["log", "dbg", "err", "dlprog", "dlstart", "dlend"]

def local_logger_factory(loglevel: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] | str = "INFO"):
	logging.basicConfig(format="[%(levelname)-8s %(asctime)s] %(message)s", datefmt="%H:%M:%S")
	logger = logging.getLogger(__name__)
	logger.setLevel(loglevel)

	def local_logger(purpose: LogPurpose, message, **kwargs):
		match purpose:
			case "log":
				logger.info(msg=message, **kwargs)
			case "dbg":
				logger.debug(msg=message, **kwargs)
			case "err":
				logger.critical(msg=message, **kwargs)
			case "dlprog" | "dlstart" | "dlend":
				logger.info(msg=message, **kwargs)
			case _:
				logger.warning(msg=f"Unknown purpose: {purpose}", **kwargs)
	return local_logger

def websocket_logger_factory(server):
	def websocket_logger(purpose: LogPurpose, data, **kwargs):
		default_message = {"type": "info"}
		full_message = {**default_message, "data": data}
		
		match purpose:
			case "log":
				server.send_message_to_all(full_message)
			case "dbg":
				server.send_message_to_all({**default_message, "type": "debug", "data": data})
			case "err":
				server.send_message_to_all({**default_message, "type": "critical", "data": data})
			case "dlprog":
				server.send_message_to_all({**full_message, "type": "progress"})
			case "dlstart":
				server.send_message_to_all({**full_message, "type": "start"})
			case "dlend":
				server.send_message_to_all({**full_message, "type": "end"})
			case _:
				print(f"Unknown purpose: {purpose}")

	return websocket_logger

