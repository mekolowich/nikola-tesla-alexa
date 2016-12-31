"""
NIKOLA -- A python application for monitoring and managing
a Tesla connected automobile from an Amazon Alexa natural language device

Authors: Michael Kolowich, Andrew Payne
Additional contributions from: Wayne Kozun
October-December, 2016

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
from threading import Timer
import time
from datetime import *
import geocoder
from dateutil.parser import parse
from isodate import parse_time

# Alexa Skill credentials are stored separately as an environment variable
APP_ID = os.environ['APP_ID']

# Hosting service looks for an 'application' callable by default.
application = Flask(__name__)
ask = Ask(application, '/')

# Tesla API connection
# Tesla Username and Password are stored separately as environment variables
TESLA_USER = os.environ['TESLA_USER']
TESLA_PASSWORD = os.environ['TESLA_PASSWORD']
tesla_connection = teslajson.Connection(TESLA_USER, TESLA_PASSWORD)
vehicle = tesla_connection.vehicles[0]

#Global State Variables
unlock_timer_state = "Off" # Start with unlock_timer_state "Off"
unlock_end_time = datetime.now() #initialize the UnlockEndTime global
unlock_timer = Timer(1,"")
charge_timer_state = "Off" # Start with charge_timer_state = "Off"
charge_start_time = datetime.now() # initialize charge_timer
charge_timer = Timer(1,"")
t = Timer(1, "")


def IdentifyStateName(abbr):
    state_name = states[abbr]
    return state_name

def GetCarTimezone(latitude, longitude):
    global timezone, timezone_corrector
    vehicle.wake_up()
    location = geocoder.google([latitude, longitude], method='timezone')
    timezone = location.timeZoneName
    timezone_corrector = (location.rawOffset + location.dstOffset) / 3600

def GetTempUnits():
    vehicle.wake_up()
    data = vehicle.data_request('gui_settings')
    if (data['gui_temperature_units'] == "F"):
        tempunits = "Fahrenheit"
    else:
        tempunits = "Celsius"
    return tempunits

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
    elif tz_adj_hour == 12: # Handles cases where adjusted time is noon
        spoken_hour = tz_adj_hour
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
    spoken_time += timezone + ", " # Add time zone to spoken time string
    return spoken_time

# Convert Temperature to Fahrenheit if necessary
def ConvertTemp(temperature, scale):
    if scale == "Fahrenheit":  # Convert to Fahrenheit if necessary
        temperature = (temperature * 1.8) + 32
    return temperature

# Function to get the inside and outside temperatures and convert to Fahrenheit if necessary
def FetchTemps(scale):
    global inside_temp, outside_temp, inside_temp_available, outside_temp_available
    vehicle.wake_up()
    data = vehicle.data_request('climate_state')
    inside_temp_available = outside_temp_available = "Yes"
    if data['inside_temp'] is None: # This handles the case in which inside/outside temperatures
        inside_temp_available = "No"
    if data['outside_temp'] is None:
        outside_temp_available = "No"
    if inside_temp_available == "Yes":
        inside_temp = 0.0
        inside_temp= ConvertTemp(data['inside_temp'], scale)
    if outside_temp_available == "Yes":
        outside_temp = 0.0
        outside_temp= ConvertTemp(data['outside_temp'], scale)
    return inside_temp, outside_temp

# Function to convert decimal hours to hours and minutes in spoken text
# Note: This is also used with seconds by dividing DecimalHours by 3600 in the function call
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
        now = datetime.now()
        charge_end_time = now + timedelta(0,(charge_minutes * 60))
        spoken_charge_time = "Your car is currently charging to a maximum of %d percent. " %data['charge_limit_soc']
        spoken_charge_time += "It should be finished charging in about %s, which would make it ready around " %SpeakDurationHM(data['time_to_full_charge'])
        spoken_charge_time += "%s." %SpeakTime(charge_end_time)
    return spoken_charge_time

# Function to speak the current inside/outside temperatures
def SpeakTemperatures():
    global inside_temp, outside_temp, inside_temp_available, outside_temp_available
    if inside_temp_available == "Yes" and outside_temp_available == "Yes":
        text = "Your car is %d degrees on the outside, " % outside_temp
        text += "and %d degrees on the inside.  In " % inside_temp
        text += "%s of course" % tempunits
    elif inside_temp_available == "No" and outside_temp_available == "No":
        text = "Temperatures are currently unavailable for your car."
    elif inside_temp_available == "Yes":
        text = "Your car is %d degrees on the inside.  Outside temperature is not currently available." % inside_temp
    else:
        text = "Your car is %d degrees on the outside.  Inside temperature is not currently available." % outside_temp
    return text

# -------------------------------------------------------------
# Intent handlers
# These are called by Alexa via flask_ask and return a string to be spoken

#INTENTS FOR CHECKING STATUS OF CAR

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

# "Where is my car?"
@ask.intent('GetLocation')
def GetLocation():
    vehicle.wake_up()
    data = vehicle.data_request('drive_state')
    latitude = data['latitude']
    longitude = data['longitude']
    location = geocoder.google([latitude, longitude], method='reverse')
    text = "Right now, your car is in %s " % location.city
    if location.country in ["US","CA","AU"]:
        text += "%s, at " % location.state_long
    else:
        text += "%s, at " % location.country
    text += "%s " % location.housenumber
    text += "%s." % location.street
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
    text = SpeakTemperatures()
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

# "What is the status of my car?"
@ask.intent('GetStatus')
def GetStatus():
    vehicle.wake_up()
    data_vehicle = vehicle.data_request('vehicle_state')
    data_charge = vehicle.data_request ('charge_state')
    FetchTemps(tempunits)
    now = datetime.now()
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
    text += SpeakTemperatures()
    text += "You have put %.1f miles on the car." % data_vehicle['odometer']
    return statement(text)

# "What's the quick brief on my car?"
@ask.intent('GetStatusQuick')
def GetStatusQuick():
    vehicle.wake_up()
    data_vehicle = vehicle.data_request('vehicle_state')
    data_charge = vehicle.data_request ('charge_state')
    FetchTemps(tempunits)
    text = "Charge is %d percent. " % data_charge['battery_level']
    text += "Rated range is %d miles, " % data_charge['battery_range']
    text += "estimated %d miles. " % data_charge['est_battery_range']
    text += "locked and " if data_vehicle['locked'] else "unlocked and "
    text += "not " if not(data_charge['charging_state']) else ""
    text += "charging. "
    text += SpeakTemperatures()
    text += "Odometer %d miles." % data_vehicle['odometer']
    return statement(text)

# INTENTS THAT SEND COMMANDS TO THE CAR

# "Unlock my car for 10 minutes."
@ask.intent('UnlockCarDuration', convert={'unlock_duration' : 'timedelta'}) # convert AMAZON.DURATION to a python timedelta object
def UnlockCarDuration(unlock_duration):
    global unlock_timer_state, unlock_end_time, unlock_timer
    vehicle.wake_up()
    data = vehicle.data_request('vehicle_state')
    now = datetime.now()
    end_time = now + unlock_duration
    if data['locked']:
        vehicle.command('door_unlock')
        unlock_timer_state = "On"
        unlock_end_time = end_time
        text = "I've unlocked your car, and it will stay unlocked for %s, until %s." % (SpeakDurationHM(unlock_duration.seconds/3600), SpeakTime(end_time + tz_adj_hour))
        data = vehicle.data_request('vehicle_state')
        unlock_timer = Timer(unlock_duration.seconds, LockCarAction) # Lock the car back up after 'minutes'
        unlock_timer.start()
    elif unlock_timer_state == "On":
        unlock_timer.cancel()
        unlock_timer = Timer(unlock_duration.seconds, LockCarAction)
        unlock_timer.start()
        text = "Your car was already on an unlock timer, but I changed it to stay unlocked "
        text += "until %s." % SpeakTime(end_time)
    else:
        text = "Your car is already unlocked.  I kept it that way."
    return statement(text)

def LockCarAction():
    vehicle.wake_up()
    vehicle.command('door_lock')
    return

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
        UnlockTimerOn = False
    # Cancel any current unlock timers
    unlock_timer_state = "Off"
    return statement(text)

# "Unlock my car."
@ask.intent('UnlockCar')
def UnlockCar():
    vehicle.wake_up()
    data = vehicle.data_request('vehicle_state')
    if not data['locked']:
        text = "Your car is already unlocked.  I kept it that way."
    else:
        vehicle.command('door_unlock')
        text = "I've unlocked your car."
    return statement(text)

# "Unlock my car until 9:00 AM."
@ask.intent('UnlockCarTime', convert={'lock_time' : 'time'})
def UnlockCarTime(lock_time):
    global unlock_timer_state, unlock_timer, unlock_timer, timezone_corrector
    vehicle.wake_up()
    data = vehicle.data_request('vehicle_state')
    # Change lock_time from purely time to datetime
    lock_time = datetime.combine(date.today(),lock_time)
    now = datetime.now()
    # Since lock_time comes in as local time and now is in UCT, need to correct for time zone
    # Also need to correct for case in which unlock_time is after midnight
    now_local = now + timedelta(hours=timezone_corrector)
    # Correct for case in which lock time is actually tomorrow
    if lock_time > now_local:
        unlock_duration = lock_time - now_local
    else:
        unlock_duration = lock_time + timedelta(hours=24) - now_local
    end_time = now + unlock_duration
    print "Lock time: " + str(lock_time)
    print "Now: " + str(now)
    print "Now-local: " + str(now_local)
    print "Unlock duration: " + str(unlock_duration)
    # If car is locked, then unlock it as requested.
    if data['locked']:
        vehicle.command('door_unlock')
        unlock_timer_state = "On"
        unlock_end_time = end_time
        text = "I've unlocked your car, and it will stay unlocked for %s, until %s." % (SpeakDurationHM(unlock_duration.seconds/3600), SpeakTime(end_time))
        data = vehicle.data_request('vehicle_state')
        unlock_timer = Timer(unlock_duration.seconds, LockCarAction) # Lock the car back up after 'minutes'
        unlock_timer.start()
    # If the unlock timer is already in effect, then reset the timer and inform the requester.
    elif unlock_timer_state == "On":
        unlock_timer.cancel()
        unlock_timer = Timer(unlock_duration.seconds, LockCarAction)
        unlock_timer.start()
        text = "Your car was already on an unlock timer, but I changed it to stay unlocked "
        text += "until %s." % SpeakTime(end_time - timedelta(hours=timezone_corrector))
    # If it's already unlocked, keep it that way, and inform the requester.
    # Note: the
    else:
        text = "Your car is already unlocked.  I kept it that way."
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
        text = "OK.  I've started charging your car. "
    text += "I'll stop when it reaches %d percent charge." %data['charge_limit_soc']
    return statement(text)

def StartChargeAction():
    global charge_timer_state
    vehicle.command('charge_stop')
    charge_timer_state = "Off"
    return

# "How long will it take to charge my car?"
@ask.intent('ChargeTime')
def ChargeTime():
    vehicle.wake_up()
    text = SpeakChargeTime()
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

# "Preheat my car"
@ask.intent('ClimateStart')
def ClimateStart():
    vehicle.wake_up()
    data = vehicle.data_request('climate_state')
    inside_temp = 0.0
    set_temp = 0.0
    inside_temp_available = "Yes"
    if data['inside_temp'] is None: # This handles the case in which inside/outside temperatures
        inside_temp_available = "No"
    if data['is_climate_on']:
        return statement("Your climate system is already running.  No need for further action.")
    elif inside_temp_available == "Yes":
        inside_temp = ConvertTemp(data['inside_temp'], tempunits)
        set_temp = ConvertTemp(data['driver_temp_setting'], tempunits)
        if abs(set_temp - inside_temp) < 5:
            text = "The inside temperature of %s degrees is already pretty close to ideal," % int(inside_temp)
            text += "so I didn't turn the climate system on, in the interest of saving energy."
        else:
            vehicle.command('auto_conditioning_start')
            if set_temp > inside_temp:
                heat_cool = "heating"
            else:
                heat_cool = "cooling"
            text = "OK, I have started %s your car " % heat_cool
            text += "to %s degrees." % int(set_temp)
    else:
        vehicle.command('auto_conditioning_start')
        set_temp = ConvertTemp(data['driver_temp_setting'], tempunits)
        text = "Current inside temperature information is unavailable for your car, but I have started the climate system as you requested."
        text =+ "It's set to %d degrees. " % set_temp
    return statement(text)

# "Stop warming my car"
@ask.intent('ClimateStop')
def ClimateStop():
    vehicle.wake_up()
    data = vehicle.data_request('climate_state')
    if not data['is_climate_on']:
        return statement("Your climate system is not running, so there's nothing to stop.")
    vehicle.command('auto_conditioning_stop')
    text = "OK, I've stopped the climate system."
    return statement(text)

# INTENTS FOR SHOWING OR STORING THE COMPLETE API DATA FOR THE CAR

# "Print out the data on my car"
@ask.intent('DataPrint')
def DataPrint():
    vehicle.wake_up()
    # Fetches the five different types of data on the car from the Tesla API
    for data_type in ('charge_state', 'drive_state', 'climate_state', 'gui_settings', 'vehicle_state'):
        data = vehicle.data_request(data_type)
        # Prints the name of the data type
        print (data_type)
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

# Get Units and Timezone for the car's location:
data = vehicle.data_request('drive_state')
latitude = data['latitude']
longitude = data['longitude']
GetCarTimezone(latitude, longitude) # TimeZone and Corrector (hours from GMT/UCT) using geocoder
tempunits = GetTempUnits()

# -------------------------------------------------------------------
# Initiate the application for the hosting environment
# This will probably vary for different hosting environments; this is for Cloud9
if __name__ == "__main__":
    host = os.getenv('IP', '0.0.0.0')
    port = int(os.getenv('PORT', 8080))
    application.debug = True
    application.run(host=host, port=port)
