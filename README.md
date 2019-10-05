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

You can find `lambda_function.py` in directory `examples/`, which will show you how you can set up an igor lambda function.
AWS lambda expects that the function being called will be a file called `lambda_function.py`, so ensure your solution has it's
entry point there. Note that the example `lambda_function.py` expects certain Environment variables (`SLACK_TOKEN`, and `OAUTH_TOKEN`), as well as the data from API gateway to be structured in a particular why.

AWS expects a `.zip` file with all dependencies and your code inside it, for the lambda function to execute, follow the steps
below to prepare the environment:

1. Create a new directory that will be zipped, ie: `mkdir -p /tmp/igor`, and go into it: `cd /tmp/igor`
2. You need to install the packages to the current location: `pip install <where igor was cloned> ./`
3. You can now add your `lambda_function.py` code, using `examples/lambda_function.py` for help/
4. Assuming you have used the examples `lambda_function.py`, you can double check things are working by running:

```sh
SLACK_TOKEN=test-token OAUTH_TOKEN="test" python3 lambda_function.py
```

5. zip igor `zip -r ../myDeploymentPackage.zip .`

### API Gateway setup - for slack

This assumes that you will be working on a slack bot. Since slack slash commands send information in the URL using url-encoding, you will need to have API gateway convert those into a dictionary srtucture that your application
can understand.

**NOTE**: When you are using API gateway, you need to re-deploy the API when you want your changes to take effect.
