import json
import boto3
from botocore.exceptions import ClientError
from typing import List, Dict
import requests
import os
from random import uniform


# A simple slack bot that allows a user easy access to start, stop, reboot and check the status of
# an instance. The slack bot works by asking is simple questions. There are 5 stats currently:
# get-instances, reboot, start, state, stop.
# /igor list-instances
#   - This will return a list of the instances, and their dns names
# /igor reboot <instance-name> <options:dry-run>
#   - This will reboot an instance by providing its name
#   - You can test this with dry-run
# /igor start <instance-name> <options:dry-run>
#   - This will start an instance by providing its name
#   - You can test this with dry-run
# /igor state <instance-name> <options:dry-run>
#   - This will return the state of an instance by providing its name
#   - You can test this with dry-run
# /igor stop <instance-name> <options:dry-run,force>
#   - This will stop an instance by providing its name
#   - You can force the stopping of an instance using force
#   - You can test this with dry-run


class PluginError(Exception):
    pass


class DryRunException(Exception):
    pass


def error_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ClientError as error:
            if "DryRunOperation" in str(error):
                raise DryRunException("Dry run was successful")
            else:
                raise PluginError(
                    "An error with the client or the instance id has been detected"
                )
        except Exception as e:
            raise PluginError("An unkown error has occured, time to panic: " + str(e))

    return wrapper


class Auth:
    def __init__(self, token=None):
        self._oauth_token = os.environ["OAUTH_TOKEN"]
        self._app_token = os.environ["SLACK_TOKEN"]
        # self._access_groups = access_groups
        if token is not None:
            self.validate_token(token)

    def validate_token(self, token):
        if token != self._app_token:
            raise ValueError("Access Denied")

    def staple_oath_token(self, data):
        data["token"] = self._oauth_token
        return data


class AwsFunctions:
    schema = {
        "instance_names": {
            "required": ["channel"],
            "switches": [],
            "help": "Returns a list of the instance names your channel can see.",
        },
        "instance_id": {"required": ["channel", "instance_name"], "switches": []},
        "instance_state": {"required": ["instance_id"], "switches": ["dry_run"]},
        "start_instance": {"required": ["instance_id"], "switches": ["dry_run"]},
        "stop_instance": {
            "required": ["instance_id"],
            "switches": ["dry_run", "force"],
        },
        "reboot_instance": {"required": ["instance_name"], "switches": ["dry_run"]},
    }

    @staticmethod
    @error_handler
    def instance_names(channel):
        client = boto3.client("ec2")
        response = client.describe_instances(
            Filters=[{"Name": f"tag:Channel_id", "Values": [channel]}]
        )
        instance_names = []
        for i in response["Reservations"]:
            if "Instances" in i:
                for j in i["Instances"]:
                    name = [tag["Value"] for tag in j["Tags"] if tag["Key"] == "Name"]
                    name = name.pop() if len(name) else ""
                    instance_names.append(name)
        return instance_names

    @staticmethod
    @error_handler
    def instance_id(channel, instance_name):
        client = boto3.client("ec2")
        response = client.describe_instances(
            Filters=[
                {"Name": "tag:Channel_id", "Values": [channel]},
                {"Name": "tag:Name", "Values": [instance_name]},
            ]
        )
        for i in response["Reservations"]:
            if "Instances" in i:
                for j in i["Instances"]:
                    return j["InstanceId"]

    @staticmethod
    @error_handler
    def instance_state(instance_id: str, dry_run: bool = False) -> str:
        client = boto3.client("ec2")
        response = client.describe_instance_status(
            InstanceIds=[instance_id], DryRun=dry_run
        )
        if len(response["InstanceStatuses"]) == 0:
            return "Instance state: stopped"
        else:
            return f'Instance state: {response["InstanceStatuses"][0]["InstanceState"]["Name"]}'

    @staticmethod
    @error_handler
    def start_instance(instance_id: str, dry_run: bool = False) -> str:
        client = boto3.client("ec2")
        response = client.start_instances(InstanceIds=[instance_id], DryRun=dry_run)
        return AwsFunctions._format_state_change(
            response["StartingInstances"], response["StartingInstances"]
        )

    @staticmethod
    @error_handler
    def stop_instance(
        instance_id: str, dry_run: bool = False, force: bool = False
    ) -> str:
        client = boto3.client("ec2")
        response = client.stop_instances(
            InstanceIds=[instance_id], DryRun=dry_run, Force=force
        )
        return AwsFunctions._format_state_change(
            response["StoppingInstances"], response["StoppingInstances"]
        )

    @staticmethod
    @error_handler
    def reboot_instance(instance_id: str, dry_run: bool = False) -> str:
        client = boto3.client("ec2")
        client.reboot_instances(InstanceIds=[instance_id], DryRun=dry_run)
        return "Instance is rebooting"

    @staticmethod
    def _format_state_change(prev: str, curr: str) -> str:
        prev = prev[0]["PreviousState"]["Name"]
        curr = curr[0]["CurrentState"]["Name"]
        if prev == curr:
            return f"Instance state has not changed from: {curr}"
        else:
            return f"Instance changing: {prev} --> {curr}"


class Igor:
    def __init__(self, channel, user_name, token):
        self._auth = Auth(token)
        self.channel = channel
        self.user = user_name
        self._plugins = {"AwsFunctions": AwsFunctions, "igor": self}

        self._peon_quotes = [
            "No time for play.",
            "Me not that kind of orc!",
            "Okie dokie.",
            "Work, work.",
            "Why you poking me again?",
            "Froedrick!",
            "I've got no body, nobody's got me. Hachachacha.",
        ]

        self.commands = {
            "list-instances": {
                "plugin": {"name": "AwsFunctions", "function": "instance_names"},
                "slack-alert": False,
            },
            "reboot": {
                "plugin": {"name": "AwsFunctions", "function": "reboot_instance"},
                "slack-alert": True,
            },
            "start": {
                "plugin": {"name": "AwsFunctions", "function": "start_instance"},
                "slack-alert": True,
            },
            "status": {
                "plugin": {"name": "AwsFunctions", "function": "instance_state"},
                "slack-alert": True,
            },
            "stop": {
                "plugin": {"name": "AwsFunctions", "function": "stop_instance"},
                "slack-alert": True,
            },
            "help": {
                "plugin": {"name": "igor", "function": "help"},
                "slack-alert": False,
            },
        }

    schema = {
        "help": {"required": [], "switches": [], "help": "A simple help function."}
    }

    def _params(self):
        return set(
            [
                i
                for i in dir(self)
                if not i.startswith("_") and not callable(getattr(self, i))
            ]
        )

    def do_this(self, message: str) -> str:
        instruction = message.split()
        command = self._parse_command(instruction[0])

        sub_commands = instruction[1:]
        pairs = {}
        key = None
        next_is_paired = False
        for i in sub_commands:
            if i.startswith("-"):
                next_is_paired = True
                key = i.replace("-", "")
            elif next_is_paired:
                pairs[key] = i
                next_is_paired = False
                key = None

        requirements = self._get_command_info(command)["required"]

        print(pairs)
        # print(requirements)
        # print(self._params())

        igor_params = self._params()
        plugin_params = set(requirements) & (set(requirements) ^ self._params())

        print(plugin_params)
        # if len(plugin_params) > len(instruction[1:]):
        #     return "Not enough arguments supplied"

        kwargs = {}
        for i in igor_params:
            kwargs[i] = getattr(self, i)

        pairs = {**pairs, **kwargs}
        data = {}
        for i in plugin_params:
            plugin = self._plugins[self.commands[command]["plugin"]["name"]]
            reqs = plugin.schema[i]["required"]
            func = getattr(plugin, i)
            req = {k: pairs[k] for k in reqs}
            data = {**data, **{i: func(**req)}}

        kwargs = {**data, **{k: pairs[k] for k in requirements if k in pairs}}

        # print(igor_params)
        # print(plugin_params)

        # kwargs = {}
        # for i in igor_params:
        #     plugin = self._plugins[self.commands[command]["plugin"]["name"]]
        #     kwargs[i] = getattr(plugin, i)

        # # for param in plugin_params:
        # #     plugin = self._plugin[self.commands[command]["plugin"]["name"]]
        # #     plugin.schema[param]

        # instance_id = (
        #     AwsFunctions.instance_id(self.channel, instruction[1])
        #     if len(instruction) > 1
        #     else ""
        # )
        # kwargs = self._get_kwarg_subcommands(command, instruction[2:])
        # kwargs = {**kwargs, **self._required_inputs(command, instance_id)}
        try:
            response = self._run_command(command, **kwargs)
            if self.commands[command]["slack-alert"]:
                self.send_slack_message(message, response)
                print(response)
                return self._peon_quotes[int(uniform(0, len(self._peon_quotes)))]
            else:
                return response
        except DryRunException as e:
            return f"Command '{command}': {str(e)}"
        except PluginError as e:
            plugin_name = self.commands[command]["plugin"]["name"]
            return f"Error with plugin {plugin_name}: " + str(e)
        except Exception as e:
            return "Error: " + str(e)

    def _required_inputs(self, command, instance_id):
        requirements = self._get_command_info(command)["required"]
        switch = {"channel": self.channel, "instance_id": instance_id}
        return {name: switch[name] for name in requirements}

    def help(self):
        msg = "Igor is your friendly worker that helps control things for you!\n"
        msg += "The currently supported commands are:\n"
        for i in self.commands:
            msg += f"{i}"
            if "help" in self._get_command_info(i):
                msg += ": " + self._get_command_info(i)["help"]
            msg += "\n"
        return msg

    def _get_command_info(self, command):
        plugin = self._plugins[self.commands[command]["plugin"]["name"]]
        return plugin.schema[self.commands[command]["plugin"]["function"]]

    def send_slack_message(self, user_message, command_response):
        message = f"""{self.user} told igor to "{user_message}".\n{command_response}"""
        data = dict(channel=self.channel, pretty=1, text=message)
        data = self._auth.staple_oath_token(data)
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        requests.post(
            "https://slack.com/api/chat.postMessage", data=data, headers=headers
        )

    def _run_command(self, command, **kwargs):
        plugin = self._plugins[self.commands[command]["plugin"]["name"]]
        func = getattr(plugin, self.commands[command]["plugin"]["function"])
        response = func(**kwargs)
        return response

    def _parse_command(self, command: str) -> str:
        if command not in self.commands:
            raise ValueError("Invalid command")
        return command

    def _get_kwarg_subcommands(self, command, provided_subcommands: List) -> Dict:
        subcommands = self._get_command_info(command)["switches"]
        # filter for commands that are valid and inject our own valid value.
        return {i: True for i in list(set(provided_subcommands) & set(subcommands))}


def lambda_handler(event, context):
    if event["command"] == "/igor":
        message = event["text"]
        user = event["user_name"]
        channel = event["channel_id"]
        token = event["token"]
        igor = Igor(channel, user, token)
        return igor.do_this(message)
    else:
        return f"Command {event['command']} is unknown"


if __name__ == "__main__":
    event = {
        "token": "test-token",
        "command": "/igor",
        "text": "stop -instance_name Test-instance",
        "user_name": "test-user",
        "channel_id": "CMQEC73B3",
    }

    print(lambda_handler(event, {}))
