import telebot
from common.constants import BOT_TOKEN, CHAT_ID, GROUP_ID
from dolphin.celery import app
bot = telebot.TeleBot(BOT_TOKEN)

@app.task(name='send_telegram_message')   
def send_telegram_message(image_url='',text=''):
    # bot.sendMessage(chat_id=GROUP_ID,text="hi")
    if image_url == '':
        bot.send_message(chat_id=GROUP_ID,text=text)
        return True
    bot.send_photo(chat_id=GROUP_ID,photo=open(image_url,"rb"),caption=text)
    return True
@app.task(name='send_telegram_sms')  
def send_telegram_sms(text):
    bot.sendMessage(chat_id=CHAT_ID, text=text)
    return True