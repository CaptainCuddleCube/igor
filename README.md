# Introduction

Igor is a simple slack bot that allows for plugins to be defined to control the instances you need controlled.

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
