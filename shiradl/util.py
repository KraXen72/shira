import json


def pprint(val):
	if isinstance(val, dict):
		d = dict(val)
		for [k, v] in d.items():
			if isinstance(v, bytes):
				d[k] = v.decode("utf-8")
		print(json.dumps(d, indent=2))
	else:
		print(val)