import webbrowser, os, subprocess
import requests
from bs4 import BeautifulSoup
from modules.audio import AudioInterface
import re, json

class Media:
    def play_youtube(self, query):
        audio = AudioInterface()
        search_query = query.replace(' ', '+')
        url = f"https://www.youtube.com/results?search_query={search_query}"
        response = requests.get(url)
        if response.status_code == 200:
            # Try lxml, fallback to html.parser
            try:
                soup = BeautifulSoup(response.text, 'lxml')
            except Exception:
                soup = BeautifulSoup(response.text, 'html.parser')
            scripts = soup.find_all('script')
            found = False
            for script in scripts:
                if 'videoRenderer' in script.text:
                    match = re.search(r'({.+})', script.text)
                    if not match:
                        continue
                    try:
                        data = json.loads(match.group(1))
                        sectionList = data['contents']['twoColumnSearchResultsRenderer']['primaryContents']['sectionListRenderer']
                        renderers = sectionList['contents'][0]['itemSectionRenderer']['contents']
                        for renderer in renderers:
                            try:
                                video = renderer['videoRenderer']
                                video_id = video['videoId']
                                video_url = f"https://www.youtube.com/watch?v={video_id}"
                                audio.speak("Playing the first YouTube result.")
                                webbrowser.open(video_url)
                                found = True
                                return
                            except Exception:
                                continue
                    except Exception:
                        continue
            if not found:
                audio.speak("No video found for your search.")
        else:
            audio.speak("Failed to search YouTube.")

    def open_file(self, path):
        if os.path.exists(path):
            if os.name=='nt':
                os.startfile(path)
            else:
                subprocess.Popen(['xdg-open',path])
