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


def error_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ClientError as error:
            if "DryRunOperation" in str(error):
                return "Dry run is successful"
            else:
                return "An error with the client or the instance id has been detected"
        except Exception as e:
            print(e)
            return "An error has occured, time to panic"

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
    @staticmethod
    @error_handler
    def get_instance_names(channel):
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
    def get_instance_id(channel, name):
        client = boto3.client("ec2")
        response = client.describe_instances(
            Filters=[
                {"Name": "tag:Channel_id", "Values": [channel]},
                {"Name": "tag:Name", "Values": [name]},
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
        self._channel = channel
        self._user = user_name
        self._exec_function_group = {"AwsFunctions": AwsFunctions}
        self._peon_quotes = [
            "No time for play.",
            "Me not that kind of orc!",
            "Okie dokie.",
            "Work, work.",
            "Why you poking me again?",
            "Froedrick!",
            "I've got no body, nobody's got me. Hachachacha.",
        ]
        self._commands = {
            "list-instances": {
                "sub-commands": [],
                "requires": ["channel"],
                "exec": {
                    "function_group": "AwsFunctions",
                    "function": "get_instance_names",
                },
                "alert": False,
            },
            "reboot": {
                "sub-commands": ["dry_run"],
                "requires": ["instance_id"],
                "exec": {
                    "function_group": "AwsFunctions",
                    "function": "reboot_instance",
                },
                "alert": True,
            },
            "start": {
                "sub-commands": ["dry_run"],
                "requires": ["instance_id"],
                "exec": {
                    "function_group": "AwsFunctions",
                    "function": "start_instance",
                },
                "alert": True,
            },
            "status": {
                "sub-commands": ["dry_run"],
                "requires": ["instance_id"],
                "exec": {
                    "function_group": "AwsFunctions",
                    "function": "instance_state",
                },
                "alert": True,
            },
            "stop": {
                "sub-commands": ["dry_run", "force"],
                "requires": ["instance_id"],
                "exec": {"function_group": "AwsFunctions", "function": "stop_instance"},
                "alert": True,
            },
        }

    def do_this(self, message: str) -> str:
        instruction = message.split()
        command = self._parse_command(instruction[0])
        instance_id = (
            AwsFunctions.get_instance_id(self._channel, instruction[1])
            if len(instruction) > 1
            else ""
        )
        kwargs = self._get_kwarg_subcommands(command, instruction[2:])
        kwargs = {**kwargs, **self._required_inputs(command, instance_id)}
        response = self._run_command(command, **kwargs)
        if self._commands[command]["alert"]:
            self.send_slack_message(message, response)
            print(response)
            return self._peon_quotes[int(uniform(0, len(self._peon_quotes)))]
        else:
            return response

    def _required_inputs(self, command, instance_id):
        requirements = self._commands[command]["requires"]
        switch = {"channel": self._channel, "instance_id": instance_id}
        return {name: switch[name] for name in requirements}

    def send_slack_message(self, user_message, command_response):
        message = f"""{self._user} told igor to "{user_message}".\n{command_response}"""
        data = dict(channel=self._channel, pretty=1, text=message)
        data = self._auth.staple_oath_token(data)
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        requests.post(
            "https://slack.com/api/chat.postMessage", data=data, headers=headers
        )

    def _run_command(self, command, **kwargs):
        func_group = self._exec_function_group[
            self._commands[command]["exec"]["function_group"]
        ]
        func = getattr(func_group, self._commands[command]["exec"]["function"])
        return func(**kwargs)

    def _parse_command(self, command: str) -> str:
        if command not in self._commands:
            raise ValueError("Invalid command")
        return command

    def _get_kwarg_subcommands(self, command, provided_subcommands: List) -> Dict:
        subcommands = self._commands[command]["sub-commands"]
        # filter for commands that are valid and inject our own valid value.
        return {
            subcommands[i]: True
            for i in list(set(provided_subcommands) & set(subcommands))
        }


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
        "text": "stop Test-instance",
        "user_name": "test-user",
        "channel_id": "channel1",
    }

    print(lambda_handler(event, {}))
