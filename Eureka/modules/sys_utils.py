import psutil, subprocess, datetime, threading, time
import requests
from utils.config import Config
import geocoder
import speedtest

class SysUtils:
    def battery(self):
        batt = psutil.sensors_battery()
        return {'percent': batt.percent, 'plugged': batt.power_plugged}

    def list_tasks(self):
        return [p.info for p in psutil.process_iter(['pid','name','cpu_percent'])]

    def set_alarm(self, at_time, callback):
        def checker():
            while True:
                if datetime.datetime.now() >= at_time:
                    callback()
                    break
                time.sleep(30)
        threading.Thread(target=checker,daemon=True).start()

    def get_time(self):
        now = datetime.datetime.now()
        # Windows uses %#I, Linux/macOS use %-I
        try:
            return now.strftime('The current time is %#I:%M %p.')
        except ValueError:
            return now.strftime('The current time is %I:%M %p.')

    def get_date(self):
        now = datetime.datetime.now()
        return now.strftime('Today is %A, %B %d, %Y.')

    def get_weather(self, city, api_key=None):
        if api_key is None:
            api_key = Config.OPENWEATHERMAP_API_KEY
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
        try:
            resp = requests.get(url)
            data = resp.json()
            if data.get('cod') != 200:
                # Fallback to Google scraping
                return self._google_weather(city)
            desc = data['weather'][0]['description']
            return f"The weather in {city.title()} is {desc}."
        except Exception:
            return self._google_weather(city)

    def get_temperature(self, city, api_key=None):
        if api_key is None:
            api_key = Config.OPENWEATHERMAP_API_KEY
        url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
        try:
            resp = requests.get(url)
            data = resp.json()
            if data.get('cod') != 200:
                # Fallback to Google scraping
                return self._google_temperature(city)
            temp = data['main']['temp']
            return f"The current temperature in {city.title()} is {temp}°C."
        except Exception:
            return self._google_temperature(city)

    def _google_temperature(self, city):
        try:
            import bs4
            from bs4 import BeautifulSoup
            search = f"temperature in {city}"
            url = f"https://www.google.com/search?q={search}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            r = requests.get(url, headers=headers)
            data = BeautifulSoup(r.text, "html.parser")
            temp = data.find("div", class_="BNeawe").text
            return f"The current temperature in {city.title()} is {temp}."
        except Exception:
            return f"Sorry, I couldn't find temperature for {city}."

    def _google_weather(self, city):
        try:
            import bs4
            from bs4 import BeautifulSoup
            search = f"weather in {city}"
            url = f"https://www.google.com/search?q={search}"
            headers = {'User-Agent': 'Mozilla/5.0'}
            r = requests.get(url, headers=headers)
            data = BeautifulSoup(r.text, "html.parser")
            temp = data.find("div", class_="BNeawe").text
            return f"The weather in {city.title()} is {temp}."
        except Exception:
            return f"Sorry, I couldn't find weather for {city}."

    def get_internet_speed(self):
        st = speedtest.Speedtest()
        st.get_best_server()
        download_speed = st.download() / 1_000_000  # Convert to Mbps
        upload_speed = st.upload() / 1_000_000  # Convert to Mbps
        return {'download': download_speed, 'upload': upload_speed}
