import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("WEATHER_KEY")
url = "https://api.openweathermap.org/data/2.5/weather"

params = {
    "q": "Ribeirao Preto,BR",
    "appid": api_key,
    "units": "metric",
    "lang": "pt_br"
}

response = requests.get(url=url, params=params, timeout=10)

print("Status:", response.status_code)
print("Resposta:", response.json())
