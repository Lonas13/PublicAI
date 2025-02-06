# Minimal conversation template

from openai import OpenAI

client = OpenAI()
messages = [{"role": "system", "content": "You are a poetic AI."}]  # Hidden system prompt

while True:
    user_input = input("You: ")  
    if user_input.lower() in {"exit", "quit"}:
        break  
    messages.append({"role": "user", "content": user_input})  

    completion = client.chat.completions.create(
        model="gpt-4o", store=True, messages=messages
    )

    response = completion.choices[0].message.content
    print("AI:", response)
    messages.append({"role": "assistant", "content": response})  # Retain context
