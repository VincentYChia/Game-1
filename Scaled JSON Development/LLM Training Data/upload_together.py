import os
from together import Together

client = Together(api_key=os.environ.get("TOGETHER_API_KEY"))

file_resp = client.files.upload(file=r"C:\Users\Vincent\PycharmProjects\Game-1\Scaled JSON Development\LLM Training Data\jsonl_outputs\adornment.jsonl", check=True)

print(file_resp.model_dump())