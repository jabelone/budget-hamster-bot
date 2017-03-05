#!/usr/bin/env python
# coding:utf-8

# Wit.ai parameters
WIT_TOKEN = '<wit-token>'
# Messenger API parameters
FB_PAGE_TOKEN = '<fb-pages-token>'
# A user secret to verify webhook get request.
FB_VERIFY_TOKEN = 'lol' #must match your webhook settings in fb developer console
#config file location
config_file = "/hamster/data.hamster"

import ConfigParser
import os
import sys
import json
from wit import Wit

import requests
from flask import Flask, request

client = Wit(access_token=WIT_TOKEN)
config = ConfigParser.ConfigParser()
config.read(config_file)

app = Flask(__name__)

@app.route('/webhook', methods=['GET'])
def verify():
    #Endpoints must be verified by Facebook, they send a random string you must send back
    if request.args.get("hub.mode") == "subscribe" and request.args.get("hub.challenge"):
        if not request.args.get("hub.verify_token") == FB_VERIFY_TOKEN:
            return "Verification token mismatch", 403
        return request.args["hub.challenge"], 200
    return "stop tryna hack mah endpoint...", 200

@app.route('/webhook', methods=['POST'])
def webhook():
    # endpoint for processing incoming messaging events
    data = request.get_json()

    if data["object"] == "page":
        for entry in data["entry"]:
            for messaging_event in entry["messaging"]:
                if messaging_event.get("message"):  # someone sent us a message
                    print(messaging_event)
                    sender_id = messaging_event["sender"]["id"]        # the facebook ID of the person sending you the message
                    recipient_id = messaging_event["recipient"]["id"]  # the recipient's ID, which should be your page's facebook ID
                    
                    if "text" in messaging_event["message"]:
                        message_text = messaging_event["message"]["text"]  # the message's text
                        process_text(sender_id, message_text)
                        
                    elif "attachments" in messaging_event["message"]:
                        message_text = "Received attachment"
                        process_text(sender_id, message_text)
                        
                    else:
                        message_text = "Sorry, I don't know how to help with that."

                if messaging_event.get("delivery"):  # delivery confirmation
                    pass

                if messaging_event.get("optin"):  # optin confirmation
                    pass

                if messaging_event.get("postback"):  # user clicked/tapped "postback" button in earlier message
                    pass

    return "ok", 200

def get_name(sender_id):
    print("Getting the name")
    
    request_url = "https://graph.facebook.com/v2.6/" + sender_id + "?access_token=" + FB_PAGE_TOKEN
    r = requests.get(request_url)
    if r.status_code == 200:
        print("json: " + str(r.json()))
        name = {"first": r.json()["first_name"], "last": r.json()["last_name"]}
        print "Got the name: " + name["first"] + " " + name["last"]
        return name
    else:
        log(r.status_code)
        log(r.text)

def check_database(sender_id):
    print(config.sections())
    if sender_id in config.sections():
        print(sender_id + " was in the config")
        
    else:
        config.add_section(sender_id)
        name = get_name(sender_id)
        config.set(sender_id, 'first_name', name["first"])
        config.set(sender_id, 'last_name', name["last"])
        with open(config_file, "wb") as configfile:
            config.write(configfile)
        print("Added " + sender_id + " to the database")

def process_text(sender_id, message_text): 
    send_read(sender_id)
    check_database(sender_id)
    first_name = config.get(sender_id, 'first_name')
    status = config.get(sender_id, 'receipt')
    
    if status == "0":
        print "Reached status 0"
        set_typing(sender_id, 1)
        resp = client.message(message_text)
        if "receipt" in resp["entities"] and "amount_of_money" in resp["entities"]:
            price = str(resp["entities"]["amount_of_money"][0]["value"])
            print("Wit thinks you want to submit a receipt worth $" + price)
            config.set(sender_id, 'receipt', "1") # 0 = new message, 1 = confirming receipt, 2 = waiting for photo, 3 = done
            with open(config_file, "wb") as configfile:
                config.write(configfile)
            send_message(sender_id, first_name + ", I think you want to submit a receipt worth $" + price + ". Is that right?")

        elif "receipt" in resp["entities"]:
            print("Wit thinks you want to submit a receipt.")
            send_message(sender_id, first_name + ", I think you want to submit a receipt but I couldn't find a price.")

        elif "amount_of_money" in resp["entities"]:
            price = str(resp["entities"]["amount_of_money"][0]["value"])
            print("Wit thinks you want to submit a receipt but only saw a price.")
            send_message(sender_id, first_name + ", I think you want to submit a receipt but I only saw a price. ($" + price + ")")

        else:
            print("Sorry, I couldn't understand that message :(")
            send_message(sender_id, "Sorry " + first_name + ", I couldn't understand that message :( - maybe try rephrasing it?")
    
    elif status == "1":
        print "Reached status 1"
        print message_text
        if "yes" in message_text:
            print("I think you said yes.")
            config.set(sender_id, 'receipt', "2") # 0 = new message, 1 = confirming receipt, 2 = waiting for photo, 3 = done
            with open(config_file, "wb") as configfile:
                config.write(configfile)
            send_message(sender_id, first_name + ", I just saved those details.  Can you please send me a photo of the receipt?")
        else:
            print("I think you said no.")
            config.set(sender_id, 'receipt', "0") # 0 = new message, 1 = confirming receipt, 2 = waiting for photo, 3 = done
            with open(config_file, "wb") as configfile:
                config.write(configfile)
            send_message(sender_id, "Ok then " + first_name + " I won't save that.  Try another query if you want.")
    
    elif status == "2":
        print "Reached status 2"
        print message_text
        if "Received attachment" in message_text:
            print("I just got a photo.")
            config.set(sender_id, 'receipt', "0") # 0 = new message, 1 = confirming receipt, 2 = waiting for photo, 3 = done
            with open(config_file, "wb") as configfile:
                config.write(configfile)
            send_message(sender_id, "Thanks for the photo " + first_name + ", I've just saved it. ")
        else:
            print("I'm super confused.")
            config.set(sender_id, 'receipt', "0") # 0 = new message, 1 = confirming receipt, 2 = waiting for photo, 3 = done
            with open(config_file, "wb") as configfile:
                config.write(configfile)
            send_message(sender_id, "I'm really sorry " + first_name + ".  I need a photo to save it but I didn't get one.  Please start again.")
    else:
        print "I got confused by the status :( "
        send_message(sender_id, "I'm really sorry " + first_name + " but I got confused by the status, please let us know by sending an email.")

def send_message(recipient_id, message_text):

    log("sending message to {recipient}: {text}".format(recipient=recipient_id, text=message_text))

    params = {  "access_token": FB_PAGE_TOKEN   }
    headers = { "Content-Type": "application/json"  }
    data = json.dumps({
        "recipient": {
            "id": recipient_id
        },
        "message": {
            "text": message_text
        }
    })
    r = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=data)
    if r.status_code != 200:
        log(r.status_code)
        log(r.text)
        
def set_typing(recipient_id, typing):

    log("setting typing status of {recipient}".format(recipient=recipient_id))

    params = {  "access_token": FB_PAGE_TOKEN   }
    headers = { "Content-Type": "application/json"  }
    if typing:
        data = json.dumps({
            "recipient": {
                "id": recipient_id
            },
            "sender_action":"typing_on"
        })
    else:
        data = json.dumps({
            "recipient": {
                "id": recipient_id
            },
            "sender_action":"typing_off"
        })
    
    r = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=data)
    if r.status_code != 200:
        log(r.status_code)
        log(r.text)

def send_read(recipient_id):
    params = {  "access_token": FB_PAGE_TOKEN   }
    headers = { "Content-Type": "application/json"  }
    data = json.dumps({
        "recipient": {
            "id": recipient_id
        },
        "sender_action":"mark_read"
    })
    
    r = requests.post("https://graph.facebook.com/v2.6/me/messages", params=params, headers=headers, data=data)
    if r.status_code != 200:
        log(r.status_code)
        log(r.text)

def log(message):  # simple wrapper for logging to stdout on heroku
    print str(message)
    sys.stdout.flush()

if __name__ == '__main__':
    app.run(port=80, debug=True)
