import anthropic

client = anthropic.Anthropic(api_key="test_key_here")
response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=10,
    messages=[{"role": "user", "content": "Hi"}]
)
print(response)