import json, os, sys

src = sys.argv[1]
out_dir = os.path.dirname(os.path.abspath(__file__))
raw = open(src, encoding="utf-8").read()
start = raw.find("{")
data = json.loads(raw[start:])
result = data.get("result", data)
if isinstance(result, str):
    result = json.loads(result)
for c in result["contracts"]:
    p = os.path.join(out_dir, c["key"] + ".json")
    json.dump(c["contract"], open(p, "w", encoding="utf-8"), indent=1)
    print(c["key"], os.path.getsize(p))
sp = os.path.join(out_dir, "ui_sweep.json")
json.dump(result["sweep"], open(sp, "w", encoding="utf-8"), indent=1)
print("ui_sweep", os.path.getsize(sp))
