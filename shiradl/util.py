import datetime
import json


def pprint(val, no_null = False):
	if not isinstance(val, dict):
		print(val)
		return
	d = {}
	for [k, v] in val.items():
		if isinstance(v, bytes):
			decoded = ""
			try: 
				decoded = v.decode("utf-8")
			except:
				decoded = "<non-utf8 bytes>"
			d[k] = decoded
		elif isinstance(v, datetime.date):
			d[k] = f"date({v.isoformat()})"
		elif v is None:
			if no_null:
				continue
			else:
				d[k] = "null" 
		else:
			try:
				json.dumps(v)
				d[k] = v
			except:
				d[k] = f"{str(type(v))} is/contains non-serializable"
	print(json.dumps(d, indent=2))
		