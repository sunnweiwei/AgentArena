from tavily import TavilyClient
import json

tavily_client = TavilyClient(api_key="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")
response = tavily_client.search("Who is Weiwei Sun?")


print(json.dumps(response, indent=2))


