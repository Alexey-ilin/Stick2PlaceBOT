import telebot
from telebot import types

import os
import redis

from flask import Flask, request

import time

TOKEN = os.environ.get("TOKEN")
r = redis.from_url(os.environ.get("REDIS_URL"))
server = Flask(__name__)

commands = {  # command description used in the "help" command
    'start': 'Get used to the bot',
    'help': 'Gives you information about the available commands',
    'add': 'Add a new location',
    'list': 'Gives your last ten locations',
    'reset': 'Clear all your locations',
}


def save_new_user(uid):
    with r.pipeline() as pipe:
        pipe.rpush(str(uid), 0)  # save user step
        # user_id: [state, counter]
        pipe.execute()


def get_user_step(uid):
    if r.exists(uid):
        return r.get(uid, 0)
    else:
        bot.send_message(uid,
                         "Seems like you dont use \"/start\" yet. So I`m gonna save you first of all...")
        save_new_user(uid)
        bot.send_chat_action(uid, 'saving')
        time.sleep(3)
        bot.send_message(uid, "Ok, lets continue")


def listener(messages):
    """
    When new messages arrive TeleBot will call this function.
    """
    for m in messages:
        if m.content_type == 'text':
            # print the sent message to the console
            print(str(m.chat.first_name) + " [" + str(
                m.chat.id) + "]: " + m.text)


def list_gen_markup(uid):
    locations = _get_last_ten_locations(uid)
    markup = types.InlineKeyboardMarkup(1)
    buttons = [types.InlineKeyboardButton(text="Hello", callback_data="Hello"),
               types.InlineKeyboardButton(text="Home", callback_data="Home"),
               types.InlineKeyboardButton(text="Work", callback_data="Work")
               ]
    for i in range(len(buttons)):
        markup.add(buttons[i])
    return markup


def _get_last_ten_locations(cid):
    locations = []
    temp_locations = r.lrange(str(cid) + ":locations", 0, 39)
    for i in range(0, len(temp_locations) - 1, 4):
        locations.append(
            {'photo_id': temp_locations[i],
             'latitude': temp_locations[i + 1],
             'longitude': temp_locations[i + 2],
             'description': temp_locations[i + 3]
             }
        )
    print(locations)
    return locations


bot = telebot.TeleBot(TOKEN)
bot.set_update_listener(listener)


# handle the "/start" command
@bot.message_handler(commands=['start'])
def command_start(m):
    cid = m.chat.id
    if not r.exists(cid):  # if user hasn't used the "/start" command yet:
        save_new_user(cid)
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


# add page
@bot.message_handler(commands=['add'])
def command_add(m):
    pipe = r.pipeline()
    cid = m.chat.id
    bot.send_message(cid,
                     "To add your place first of all send me the brief description")
    try:
        bot.register_next_step_handler(m, process_description_step, pipe=pipe)
    except Exception as exc:
        bot.send_message(cid, "Oops, something went wrong.")
        bot.send_message(cid, "Please, try again")
        pipe.reset()


# 2nd step of adding your place - description of it
def process_description_step(m, pipe):
    try:
        cid = m.chat.id
        if m.content_type != 'text':
            raise Exception()
        description = m.text
        pipe.lpush(str(cid) + ":locations", description)
        bot.send_message(cid, 'Ok, please send the location of it')
        bot.register_next_step_handler(m, process_location_step, pipe=pipe)
    except Exception as exc:
        bot.send_message(cid, "Oops, something went wrong.")
        bot.send_message(cid, "Please, try again")
        pipe.reset()


# 3rd step - adding location
def process_location_step(m, pipe):
    try:
        cid = m.chat.id
        if m.content_type != 'location':
            raise Exception()
        latitude = m.location.latitude
        longitude = m.location.longitude
        pipe.lpush(str(cid) + ":locations", longitude)
        pipe.lpush(str(cid) + ":locations", latitude)
        bot.send_message(cid, 'Good, please send the photo of your place')
        bot.register_next_step_handler(m, process_photo_step, pipe=pipe)
    except Exception as exc:
        bot.send_message(cid, "Oops, something went wrong.")
        bot.send_message(cid, "Please, try again")
        pipe.reset()


# the last step - adding photo
def process_photo_step(m, pipe):
    try:
        cid = m.chat.id
        if m.content_type != 'photo':
            raise Exception()
        print(m.photo)
        photo = m.photo[-1].file_id
        pipe.lpush(str(cid) + ":locations", photo)
        pipe.execute()
        bot.send_message(cid, "Success. Your location is saved")
    except Exception as exc:
        bot.send_message(cid, "Oops, something went wrong.")
        bot.send_message(cid, "Please, try again")
        pipe.reset()


@bot.message_handler(commands=['reset'])
def command_reset(m):
    try:
        cid = m.chat.id
        r.delete(str(cid) + ":locations")
    except Exception as exc:
        bot.send_message(cid, "Oops, something went wrong.")
        bot.send_message(cid, "Please, try again")


@bot.message_handler(commands=['list'])
def command_list(m):
    try:
        cid = m.chat.id
        num_locations = r.llen(str(cid) + ':locations') // 4
        bot.send_message(cid,
                         f"You have {num_locations} saved locations. Here they are",
                         reply_markup=list_gen_markup(cid))

    except Exception as exc:
        bot.send_message(cid, "Oops, something went wrong.")
        bot.send_message(cid, "Please, try again")


@bot.message_handler(func=lambda message: True, content_types=['text'])
def command_default(m):
    # this is the standard reply to a normal message
    bot.send_message(m.chat.id,
                     "I don't understand \"" + m.text + "\"\nMaybe try the help page at /help")


@server.route('/bot', methods=['POST'])
def getMessage():
    bot.process_new_updates(
        [telebot.types.Update.de_json(request.stream.read().decode("utf-8"))])
    return "!", 200


@server.route('/')
def webhook():
    bot.remove_webhook()
    bot.set_webhook(url="https://stick2placebot.herokuapp.com/bot")
    return "!", 200


server.run(host="0.0.0.0", port=int(os.environ.get('PORT', 5000)))
