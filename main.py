import telebot
from telebot import types

import os
import redis

from flask import Flask, request

TOKEN = "1373309629:AAE5X1NvcdzycQVv8XyIPxPsFGmPHasFUYw"
r = redis.from_url(os.environ.get("REDIS_URL"))
server = Flask(__name__)

commands = {  # command description used in the "help" command
    'start': 'Get used to the bot',
    'help': 'Gives you information about the available commands',
    'add': 'Add a new location',
    'list': 'Gives your last ten locations',
    'reset': 'Clear all your locations',
}


def listener(messages):
    """
    When new messages arrive TeleBot will call this function.
    """
    for m in messages:
        if m.content_type == 'text':
            # print the sent message to the console
            print(str(m.chat.first_name) + " [" + str(
                m.chat.id) + "]: " + m.text)


bot = telebot.TeleBot(TOKEN)
bot.set_update_listener(listener)


# handle the "/start" command
@bot.message_handler(commands=['start'])
def command_start(m):
    cid = m.chat.id
    if not r.exists(cid):  # if user hasn't used the "/start" command yet:
        r.set(cid, 0)  # save user id and state
        r.set(cid + "_counter", 0)
        bot.send_message(cid, f"Hello, {m.chat.first_name}, lets start")
        bot.send_message(cid, "Scanning complete, I know you now")
        command_help(m)  # show the new user the help page
    else:
        bot.send_message(cid,
                         "I already know you, no need for me to scan you again!")


# help page
@bot.message_handler(commands=['help'])
def command_help(m):
    cid = m.chat.id
    help_text = "The following commands are available: \n"
    for key in commands:  # generate help text out of the commands dictionary defined at the top
        help_text += "/" + key + ": "
        help_text += commands[key] + "\n"
    bot.send_message(cid, help_text)  # send the generated help page


@bot.message_handler(func=lambda message: True, content_types=['text'])
def command_default(m):
    # this is the standard reply to a normal message
    bot.send_message(m.chat.id,
                     "I don't understand \"" + m.text + "\"\nMaybe try the help page at /help")


@server.route('/' + TOKEN, methods=['POST'])
def getMessage():
    bot.process_new_updates(
        [types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!", 200


@server.route('/')
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url="https://stick2placebot.herokuapp.com/" + TOKEN)
    return "!", 200


if __name__ == "__main__":
    server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
