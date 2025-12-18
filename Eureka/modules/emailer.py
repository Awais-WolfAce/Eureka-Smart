import smtplib
from email.mime.text import MIMEText
from utils.config import Config

class Emailer:
    def send(self, to, subject, body):
        msg = MIMEText(body)
        msg['Subject'] = subject
        msg['From']    = Config.EMAIL_USER
        msg['To']      = to
        with smtplib.SMTP_SSL('smtp.gmail.com',465) as smtp:
            smtp.login(Config.EMAIL_USER, Config.EMAIL_PASS)
            smtp.send_message(msg)
