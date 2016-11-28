"""
NIKOLA -- A python application for monitoring and managing
a Tesla connected automobile from an Amazon Alexa natural language device

Authors: Michael Kolowich, Andrew Payne
October/November, 2016

Requires:
teslajson.py by Greg Glockner (on GitHub)
flask_ask by John Wheeler (on GitHub)
!/usr/bin/python
"""
#import necessary components
import os
from flask import Flask, request, jsonify
from flask_ask import Ask, statement
import teslajson
import threading
import time
import datetime

# Alexa Skill credentials are stored separately as an environment variable
APP_ID = os.environ['APP_ID']

# Hosting service looks for an 'application' callable by default.
application = Flask(__name__)
ask = Ask(application, '/')

# Tesla API connection
# Tesla Username and Password are stored separately as environment variables
TESLA_USER = os.environ['TESLA_USER']
TESLA_PASSWORD = os.environ['TESLA_PASSWORD']
tesla_connection = teslajson.Connection("TESLA_USER", "TESLA_PASSWORD")
vehicle = tesla_connection.vehicles[0]

# Get environment variables
# Timezone and Corrector (hours from GMT/UCT):
timezone_corrector = int(os.environ['TIMEZONE_CORRECTOR'])
timezone = os.environ['TIMEZONE']
#Unit Scales (temperature, distance, etc.)
tempunits = str(os.environ['TEMPUNITS'])

# Returns the spoken time of day in the current time zone
def SpeakTime(time_to_speak):
    tz_adj_hour = time_to_speak.hour + timezone_corrector
    if tz_adj_hour < 0: # Handles cases where adjusted time is less than zero
        spoken_hour = tz_adj_hour + 12
        AM_PM = "PM"
    elif tz_adj_hour == 0: # Handles case where adjusted time is midnight
        spoken_hour = 12
        AM_PM = "AM"
    elif tz_adj_hour > 12: # Handles cases where adjusted time is afternoon/evening
        spoken_hour = tz_adj_hour - 12
        AM_PM = "PM"
    else:
        spoken_hour = tz_adj_hour # Handles cases where adjusted time is morning
        AM_PM = "AM"
    spoken_time = "%d " % spoken_hour # Add the hour to the spoken time string
    if time_to_speak.minute == 0: # Handle 'on the hour' case
        spoken_minute = "o-clock"
    elif time_to_speak.minute < 10: # Handle single-digit minutes case
        spoken_minute = "oh " + str(time_to_speak.minute)
    else:
        spoken_minute = str(time_to_speak.minute)
    spoken_time += spoken_minute + " " # Add minutes to spoken time string
    # Need to find out a better way for Alexa to articulate "AM" and "PM"
    if AM_PM == "AM":
        spoken_time += " ay em "
    else:
        spoken_time += " pee em "
    spoken_time += timezone + " Time, " # Add time zone to spoken time string
    return spoken_time

# Function to get the inside and outside temperatures and convert to Fahrenheit if necessary
def FetchTemps(scale):
    global inside_temp, outside_temp
    vehicle.wake_up()
    data = vehicle.data_request('climate_state')
    inside_temp = 0.0
    outside_temp = 0.0
    inside_temp= data['inside_temp'] # Temps come back from Tesla in Celsius
    outside_temp= data['outside_temp']
    if scale == "Fahrenheit":  # Convert to Fahrenheit if necessary
        inside_temp = (inside_temp * 1.8) + 32
        outside_temp = (outside_temp * 1.8) + 32
    return inside_temp, outside_temp

# Function to convert decimal hours to hours and minutes in spoken text
def SpeakDurationHM(DecimalHours):
    int_hrs = int(DecimalHours)
    int_mins = int((DecimalHours - float(int_hrs)) * 60)
    if int_hrs == 0:
        spoken_duration = ""
    else:
        if int_hrs == 1:
            spoken_duration = "%d hour" %int_hrs
        else:
            spoken_duration = "%d hours" %int_hrs
    if int_mins > 0:
        if int_hrs > 0:
            spoken_duration += " and "
        spoken_duration += " %d minutes" %int_mins
    return spoken_duration

# Function to speak the expected time to reach the charge limit
def SpeakChargeTime():
    vehicle.wake_up()
    data = vehicle.data_request('charge_state')
    spoken_charge_time = ""
    if (data['charging_state'] == "Charging"):
        charge_minutes = int(data['time_to_full_charge'] * 60)
        now = datetime.datetime.now()
        charge_end_time = now + datetime.timedelta(0,(charge_minutes * 60))
        spoken_charge_time = "Your car is currently charging to a maximum of %d percent. " %data['charge_limit_soc']
        spoken_charge_time += "It should be finished charging in about %s, which would make it ready around " %SpeakDurationHM(data['time_to_full_charge'])
        spoken_charge_time += "%s." %SpeakTime(charge_end_time)
    return spoken_charge_time

# -------------------------------------------------------------
# Intent handlers
# These are called by Alexa via flask_ask and return a string to be spoken

# "What is the charge level of my car?"
@ask.intent('GetChargeLevel')
def GetChargeLevel():
    vehicle.wake_up()
    data = vehicle.data_request('charge_state')
    text = "Your current charge level is %d percent, " % data['battery_level']
    text += "and your rated range is %d miles. " % data['battery_range']
    text += SpeakChargeTime()
    return statement(text)

# "What does my odometer read?"
@ask.intent('GetOdometer')
def GetOdometer():
    vehicle.wake_up()
    data = vehicle.data_request('vehicle_state')
    text = "Your odometer reading is %.1f miles." % data['odometer']
    return statement(text)

# "How far can I drive?"
@ask.intent('GetRange')
def GetRange():
    vehicle.wake_up()
    data = vehicle.data_request('charge_state')
    text = "Your car's EPA rated range is %d miles, " % data['battery_range']
    text += "but based on your recent driving patterns, your estimated range is %d miles." % data['est_battery_range']
    return statement(text)

# "What is the temperature of my car?"
@ask.intent('GetTemperatures')
def GetTemperatures():
    FetchTemps(tempunits)
    text = "Your car is %d degrees on the outside, " % outside_temp
    text += "and %d degrees on the inside.  In " % inside_temp
    text += "%s of course" % tempunits
    return statement(text)

# "Is my car locked?"
@ask.intent('GetLocked')
def GetLocked():
    vehicle.wake_up()
    data = vehicle.data_request('vehicle_state')
    text = "Your car is "
    if data['locked']:
        text += "locked "
    else:
        text += "unlocked "
    text += "at the moment."
    return statement(text)

# "What is the status of my car?"
@ask.intent('GetStatus')
def GetStatus():
    vehicle.wake_up()
    data_vehicle = vehicle.data_request('vehicle_state')
    data_charge = vehicle.data_request ('charge_state')
    FetchTemps(tempunits)
    now = datetime.datetime.now()
    text = "As of "
    text += SpeakTime(now)
    text += "your charge level is %d percent. " % data_charge['battery_level']
    text += "Your car's EPA rated range is %d miles, " % data_charge['battery_range']
    text += "but based on your recent driving patterns, your estimated range is %d miles. " % data_charge['est_battery_range']
    text += "It's currently "
    text += "locked"
    if not(data_charge['charging_state'] == "Charging"):
       text += " and it's not charging. "
    else:
       text += ". "
       text += SpeakChargeTime()
    text += "At the moment, your car is %d degrees " % outside_temp
    text += "%s outside " %tempunits
    text += "and %d degrees on the inside. " % inside_temp
    text += "You have put %.1f miles on the car." % data_vehicle['odometer']
    return statement(text)

# "What's the quick brief on my car?"
@ask.intent('GetStatusQuick')
def GetStatusQuick():
    vehicle.wake_up()
    data_vehicle = vehicle.data_request('vehicle_state')
    data_charge = vehicle.data_request ('charge_state')
    FetchTemps('tempunits')
    text = "Charge is %d percent. " % data_charge['battery_level']
    text += "Rated range is %d miles, " % data_charge['battery_range']
    text += "estimated %d miles. " % data_charge['est_battery_range']
    text += "locked and " if data_vehicle['locked'] else "unlocked and "
    text += "not " if not(data_charge['charging_state']) else ""
    text += "charging. "
    text += "Outside temp %d degrees " % outside_temp
    text += "%s " % tempunits
    text += "and inside %d degrees. " % inside_temp
    text += "Odometer %d miles." % data_vehicle['odometer']
    return statement(text)

# "Is my car locked?"
@ask.intent('UnlockCar')
def UnlockCar():
    vehicle.wake_up()
    data = vehicle.data_request('vehicle_state')
    text = "I've unlocked your car." if data['locked'] else "Your car is already unlocked.  I kept it that way."
    return statement(text)

# "Lock my car."
def LockDoor():
    vehicle.wake_up()
    vehicle.command('door_unlock')

# "Unlock my car for x minutes."
@ask.intent('UnlockCarDuration', convert={'mins' : int})
def UnlockCarDuration(mins):
    vehicle.wake_up()
    data = vehicle.data_request('vehicle_state')
    duration_seconds = mins * 60
    now = datetime.datetime.now()
    end_time = now + datetime.timedelta(0,(mins * 60))
    if data['locked']:
        vehicle.command('door_unlock')
        text = "I've unlocked your car, and it will stay unlocked for %d minutes, until %s." % (mins, SpeakTime(end_time))
        t = threading.Timer(int(duration_seconds), LockDoor)
        t.start()
    else:
        text += "Your car is already unlocked.  I kept it that way."
    return statement(text)

# "Lock my car."
@ask.intent('LockCar')
def LockCar():
    vehicle.wake_up()
    data = vehicle.data_request('vehicle_state')
    if data['locked']:
        text = "Your car is already locked.  I kept it that way."
    else:
        vehicle.command('door_lock')
        text = "I've locked your car."
    return statement(text)

# "Stop charging my car."
@ask.intent('ChargeStop')
def ChargeStop():
    vehicle.wake_up()
    data = vehicle.data_request('charge_state')
    if (data['charging_state'] == "Charging"):
        vehicle.command('charge_stop')
        text = "OK. I stopped charging. "
    else:
        text = "Sorry, but you car isn't charging, so I can't stop it. "
    text += "Your current charge level is %d percent, " % data['battery_level']
    text += "and your rated range is %d miles." % data['battery_range']
    return statement(text)

# "Start charging my car."
@ask.intent('ChargeStart')
def ChargeStart():
    vehicle.wake_up()
    data = vehicle.data_request('charge_state')
    if (data['charging_state'] == "Charging"):
        text = "Your car is already charging. "
    else:
        vehicle.command('charge_start')
        text = "OK.  I've started charging your car."
    text += "I'll stop when it reaches %d percent charge." %data['charge_limit_soc']
    return statement(text)

# "How long will it take to charge my car?"
@ask.intent('ChargeTime')
def ChargeTime():
    vehicle.wake_up()
    text = SpeakChargeTime()
    return statement(text)

# "Is my car plugged in?"
@ask.intent('GetPluggedIn')
def GetPluggedIn():
    data = vehicle.data_request('charge_state')
    if data['charge_port_door_open']:
        text = "Your car is plugged in, "
        if (data['charge_state'] == "Charging"):
            text += "and it's charging."
        else:
            text += "but it's not charging."
    else:
        text = "No, your car is not plugged in right now."
    return statement(text)

# "Set the charge level to x percent on my car."
@ask.intent('ChargeSet', convert={'limit' : int})
def ChargeSet(limit):
    vehicle.wake_up()
    data = vehicle.data_request('charge_state')
    new_limit = limit
    old_limit = data['charge_limit_soc']
    vehicle.command('set_charge_limit', {'percent' : new_limit})
    data = vehicle.data_request('charge_state')
    if old_limit > new_limit:
        text = "I've reduced your charge limit from %d percent " %old_limit
        text += "to %d percent. " %new_limit
    else:
        text = "I've increased your charge limit from %d percent " %old_limit
        text += "to %d percent. " %new_limit
    if data['battery_level'] > new_limit:
        text += "Please note, however, that your battery is already charged higher than that level, at %d percent." %data['battery_level']
    return statement(text)

# "Print out the data on my car"
@ask.intent('DataPrint')
def DataPrint():
    vehicle.wake_up()
    # Fetches the five different types of data on the car from the Tesla API
    for data_type in ('charge_state', 'drive_state', 'climate_state', 'gui_settings', 'vehicle_state'):
        data = vehicle.data_request(data_type)
        # Prints the name of the data type
        print data_type
        # Prints to the console each key and value for the type of car data
        for (k, val) in sorted(data.items()):
            print "   %-40s %s" % (k,val)
    return statement("OK.  You can check your car's data on the application console.")

# "Dump the data on my car."
@ask.intent('DataDump')
def DataDump():
    vehicle.wake_up()
    # Delete the tesladata.txt file, then open it for writing
    os.remove("tesladata.txt")
    f = open("tesladata.txt", "w")
    for data_type in ('charge_state', 'drive_state', 'climate_state', 'gui_settings', 'vehicle_state'):
        data = vehicle.data_request(data_type)
        #Dumps to file the name of the data type
        f.write(data_type + "\n")
        # Dumps to file each key and value for the type of car data
        for (k, val) in sorted(data.items()):
            f.write("   %-40s %s" % (k,val))
            f.write("\n")
        f.write("\n")
    f.close()
    return statement("OK.  I have written your car's data to a file.")

# Function in Process
# Gets Car ready by charging via climate control
# drive_type is long or normal (this sets target charge for 100% and 90%, respectively)
#@ask.intent('GetCarReady', convert={'ready_time' : ##WhatUnitsHere?##, }, drive_type)
#def GetCarReady(ready_time):
#    vehicle.wake_up()
#    data_vehicle = vehicle.data_request('vehicle_state')
#    data = vehicle.data_request('charge_state')
    # Determine how long it will take to charge (100% if long drive)

#    EstimateChargeTime()
    # Is there enough time?  Inform the user if not
    # Set up a task to start charging at
#    return statement(text)

# -------------------------------------------------------------------
# Initiate the application for the hosting environment
# This will probably vary for different hosting environments; this is for Cloud9
if __name__ == "__main__":
    host = os.getenv('IP', '0.0.0.0')
    port = int(os.getenv('PORT', 8080))
    application.debug = True
    application.run(host=host, port=port)
