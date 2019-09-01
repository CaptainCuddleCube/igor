import json
import boto3
from botocore.exceptions import ClientError
from typing import List, Dict
import requests
import os


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
# print(instance_state(instance["id"], False))
# print(start_instance(instance["id"], False))
# print(stop_instance(instance["id"], False))
# print(list_instances(INSTANCES["token1"]))


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


class InstanceGroups:
    def __init__(self, instances):
        self._instances = instances

    def get_group(self, group_name):
        return self._instances.get(group_name, [])


class Auth:
    def __init__(self, access_groups, oauth="", app_token=""):
        self._app_token = oauth if oauth != "" else os.environ["OAUTH_TOKEN"]
        self._oauth_token = app_token if app_token else os.environ["APP_TOKEN"]
        self._access_groups = access_groups

    def validate_token(self, token):
        if token != self._app_token:
            raise ValueError("Access Denied")

    def get_resource_groups(self, channel):

        if not set([channel]) & set(self._access_groups):
            raise ValueError("Access Denied")
        channel_resources = self._access_groups.get(channel, "")
        return channel_resources

    def staple_oath_token(self, data):
        data["token"] = self._oauth_token
        return data


class Igor:
    def __init__(self, auth, channel, user_name, instances):
        self._auth = auth
        self._channel = channel
        self._user = user_name
        self._instance_groups = instances
        dry_run = {"dry-run": "dry_run"}
        force = {"force": "force"}
        self._commands = {
            "list-instances": {
                "sub-commands": {},
                "exec": self._list_instances,
                "alert": False,
            },
            "reboot": {
                "sub-commands": dry_run,
                "exec": self._reboot_instance,
                "alert": True,
            },
            "start": {
                "sub-commands": dry_run,
                "exec": self._start_instance,
                "alert": True,
            },
            "status": {
                "sub-commands": dry_run,
                "exec": self._instance_state,
                "alert": True,
            },
            "stop": {
                "sub-commands": {**dry_run, **force},
                "exec": self._stop_instance,
                "alert": True,
            },
        }

    def do_this(self, message: str) -> str:
        instruction = message.split()
        command = self._parse_command(instruction[0])
        instance_id = (
            self._get_instance_id(instruction[1]) if len(instruction) > 1 else ""
        )
        kwargs = self._get_kwarg_subcommands(command, instruction[2:])
        kwargs = {**kwargs, "instance_id": instance_id}
        response = self._run_command(command, **kwargs)
        if self._commands[command]["alert"]:
            self._send_slack_message(message, response)
        return response

    def _send_slack_message(self, user_message, command_response):
        message = f"""Master {self._user} told igor to {user_message}.
                  Making this output: {command_response}"""
        data = dict(channel=self._channel, pretty=1, text=message)
        data = self._auth.staple_oath_token(data)
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        reponse = requests.post(
            "https://slack.com/api/chat.postMessage", data=data, headers=headers
        )

    def _run_command(self, command, **kwargs):
        return self._commands[command]["exec"](**kwargs)

    def _format_state_change(self, prev: str, curr: str) -> str:
        if prev == curr:
            return f"Instance state has not changed from: {curr}"
        else:
            return f"Changing instande state: {prev} --> {curr}"

    @error_handler
    def _instance_state(self, instance_id: str, dry_run: bool = False, **kwargs) -> str:
        client = boto3.client("ec2")
        response = client.describe_instance_status(
            InstanceIds=[instance_id], DryRun=dry_run
        )
        if len(response["InstanceStatuses"]) == 0:
            return "Instance state: stopped"
        else:
            return f'Instance state: {response["InstanceStatuses"][0]["InstanceState"]["Name"]}'

    @error_handler
    def _start_instance(self, instance_id: str, dry_run: bool = False, **kwargs) -> str:
        client = boto3.client("ec2")
        response = client.start_instances(InstanceIds=[instance_id], DryRun=dry_run)
        return self._format_state_change(
            response["StartingInstances"][0]["PreviousState"]["Name"],
            response["StartingInstances"][0]["CurrentState"]["Name"],
        )

    @error_handler
    def _stop_instance(
        self, instance_id: str, dry_run: bool = False, force: bool = False, **kwargs
    ) -> str:
        client = boto3.client("ec2")
        response = client.stop_instances(
            InstanceIds=[instance_id], DryRun=dry_run, Force=force
        )
        return self._format_state_change(
            response["StoppingInstances"][0]["PreviousState"]["Name"],
            response["StoppingInstances"][0]["CurrentState"]["Name"],
        )

    @error_handler
    def _reboot_instance(
        self, instance_id: str, dry_run: bool = False, **kwargs
    ) -> str:
        client = boto3.client("ec2")
        client.reboot_instances(InstanceIds=[instance_id], DryRun=dry_run)
        return "Instance is rebooting"

    def _get_resources(self):
        resource_group = self._auth.get_resource_groups(self._channel)
        return self._instance_groups.get_group(resource_group)

    def _get_instance_id(self, instance_name: str) -> str:
        instance_id = {
            i["id"] for i in self._get_resources() if instance_name == i["name"]
        }
        if len(instance_id) == 0:
            return ""

        return list(instance_id)[0]

    def _list_instances(self, **kwargs) -> str:
        return ", ".join([f'{i["name"]}' for i in self._get_resources()])

    def _parse_command(self, command: str) -> str:
        if command not in self._commands:
            raise ValueError("Invalid command")
        return command

    def _get_kwarg_subcommands(self, command, possible_subcommands: List) -> Dict:
        subcommands = self._commands[command]["sub-commands"]
        # filter for commands that are valid and inject our own valid value.
        return {
            subcommands[i]: True
            for i in list(set(possible_subcommands) & set(subcommands))
        }


def lambda_handler(event, context):
    if event["command"] == "/igor":
        with open("access_groups.json", "r") as file:
            access_groups = json.load(file)
            auth = Auth(access_groups)
        with open("instance_groups.json", "r") as file:
            instance_groups = InstanceGroups(json.load(file))

        message = event["text"]
        user = event["user_name"]
        channel = event["channel_id"]
        token = event["token"]

        igor = Igor(auth, channel, user, instance_groups)
        return igor.do_this(message)
    else:
        return f"Command {event['command']} is unknown"


if __name__ == "__main__":
    event = {
        "token": "test-token",
        "command": "/igor",
        "text": "list-instances instance",
        "user_name": "test-user",
        "channel_id": "channel1",
        "token": "test-token",
    }

    print(lambda_handler(event, {}))
