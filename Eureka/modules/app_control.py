import subprocess
import os
import platform

class AppControl:
    def open_app(self, command):
        if platform.system()=='Windows':
            os.startfile(command)
        else:
            subprocess.Popen(command.split())

    def close_app(self, name):
        if platform.system()=='Windows':
            subprocess.call(['taskkill','/IM',name,'/F'])
        else:
            subprocess.call(['pkill',name])
