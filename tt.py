from google import genai

client = genai.Client(api_key="AIzaSyBZ9jDqQSJgHu53kUIlnK2gTFaTH5Hobyw")

for model in client.models.list():
    print(model.name)
