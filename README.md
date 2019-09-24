# Introduction

Igor is a simple slack bot that allows for plugins to be defined to control the instances you need controlled.

## Igor

Igor is the base class that essentially parses commands, and runs plugin functions.

Igor has a built in help function that can be overrided.

## Plugins

Plugins are broken down into built in and contrib plugins.

### Contrib

#### Aws

Igor has simple slack conrol that help's start, stop, reboot and check the status of
an instance.

There are 5 stats currently:
get-instances, reboot, start, state, stop.

- /igor list-instances
  - This will return a list of the instances, and their dns names
- /igor reboot <instance-name> <options:dry-run>
  - This will reboot an instance by providing its name
  - You can test this with dry-run
- /igor start <instance-name> <options:dry-run>
  - This will start an instance by providing its name
  - You can test this with dry-run
- /igor status <instance-name> <options:dry-run>
  - This will return the state of an instance by providing its name
  - You can test this with dry-run
- /igor stop <instance-name> <options:dry-run,force>
  - This will stop an instance by providing its name
  - You can force the stopping of an instance using force
  - You can test this with dry-run

## Lambda function and AWS API gateway

Installing this application and using the AWS Api gateway is a sane way to have conrtol of your AWS infra.

This will be a guide to reveal how you can setup things on your side.

### AWS lambda setup

You will need to create a .zip file that includes all the packages that you will require to have the code run.
Your entrance script will be run from a function called lambda_function.py, and that will be executed.

You can find `lambda_function.py` in directory `examples/`, which will show you how you can set things up.

### API Gateway setup - for slack

This assumes that you will be working on a slack bot. Since slack slash commands send information in the URL using url-encoding, you will need to have API gateway convert those into a dictionary srtucture that your application
can understand.

**NOTE**: When you are using API gateway, you need to re-deploy things if you want to make changes.
