# Nikola

Nikola is a python application for monitoring and managing
a Tesla connected automobile from an Amazon Alexa natural language device

Authors: Michael Kolowich, Andrew Payne;
Additional contributions: Wayne Kozun
October/November, 2016

Requires:
* teslajson.py by Greg Glockner (on GitHub);
* flask_ask by John Wheeler (on GitHub);
* geocoder by Denis Carriere (on GitHub)

## Notes
The Python program application.py contains the intent handlers required to
accept an Alexa Intent, query and post to the Tesla API for a specific car,
and return a text response to be spoken on Alexa devices such as the Echo and Dot.

The Alexa skill we designed has not been published because we have not (yet)
deployed a public server and a way to handle credentials for multiple cars.
We have, however, included two files -- intents.txt and utterances.txt -- that
would allow an Alexa intent to be deployed easily by anyone who sets up an
Amazon developer account.

The following need to be entered as Environment Variables because they contain
private information:
* TESLA_USER: Tesla.com username for the Tesla automobile to be monitored and managed;
* TESLA_PASSWORD: Tesla.com password;
* APP_ID: App ID for the Alexa app that you create.

The function DataDump() creates a file named tesladata.txt, which contains a
complete dump of the data provided by the Tesla API.  An example of this file is
provided in this repository.  (Note: location and vehicle name data is deleted
for privacy reasons.)

## Deploying the Nikola Skill using Cloud9
I have written up a procedure on how to deploy the Nikola skill on a personal instance
of the Amazon developer console and a free server instance on Cloud9.  Included are
instructions on how to provision a free Cloud9 account and the steps to take in order to
get the application/skill up and running.  You will find this in the file: how-to-cloud9.txt.
Please note that free instances of Cloud9 terminate after two hours; paid accounts will
run indefinitely.

## Key Files in this repository
Here are the most important files and what they do:
* <b>application.py</b> is the main Python program to handle the incoming Alexa intents, query the Tesla API, issue commands through the API, formulate and return responses to be spoken by an Alexa device;
* <b>teslajson.py</b> is the third-party application, written by Greg Glockner, that actually handles the communications to and from the Tesla through the API;
* <b>intents.txt</b> is the most current schema of intents, in JSON format, that defines the inquiries and commands that Alexa can pass to Nikola.  This can be copied and pasted into the "Intent Schema" section of the "Interaction Model" tab for a Nikola Skill that can be defined and managed in the Amazon Developer Console.
* <b>utterances</b> is a list of "Sample Utterances" that Alexa uses to decide which intent to send to the application.  Like the Intent Schema, this can be copied and pasted into the "Sample Utterances" section of the Interaction Model for an Alexa Skill;
* <b>tesladata.txt</b> is, for reference purposes, a dump of API data from a Tesla Model X running v8.0 of the Tesla firmware as of November, 2016.  This list may be generated for any Tesla automobile at any time by invoking the "DataDump" intent by saying: "Alexa, ask Nikola to dump my car's data to a file."

## Credits
Much credit goes to [Tim Dorr](http://timdorr.com) for documenting the Tesla JSON API.
Also to Greg Glockner for his teslajson.py approach to unlocking that API's power.

## Disclaimer
This software is provided as-is.  This software is not supported by or
endorsed by Tesla Motors.  Tesla Motors does not publicly support the
underlying JSON API, so this software may stop working at any time.  The
author makes no guarantee to release an updated version to fix any
incompatibilities.
