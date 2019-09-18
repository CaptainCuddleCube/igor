import json
from typing import List, Dict
import os
from igor import Igor
from plugins.aws import AwsFunctions


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


def lambda_handler(event, context):
    if event["command"] == "/igor":
        message = event["text"]
        user = event["user_name"]
        channel = event["channel_id"]
        token = event["token"]
        auth = Auth(token)
        plugins = {"AwsFunctions": AwsFunctions(channel)}
        commands = {
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
        igor = Igor(channel, user, auth, plugins, commands)
        return igor.do_this(message)
    else:
        return f"Command {event['command']} is unknown"


if __name__ == "__main__":
    event = {
        "token": "test-token",
        "command": "/igor",
        "text": "status Test-instance",
        "user_name": "test-user",
        "channel_id": "ABCDE33",
    }
    print(lambda_handler(event, {}))
    event = {
        "token": "test-token",
        "command": "/igor",
        "text": "status --instance_name Test-instance",
        "user_name": "test-user",
        "channel_id": "ABCDE33",
    }
    print(lambda_handler(event, {}))
    event = {
        "token": "test-token",
        "command": "/igor",
        "text": "help",
        "user_name": "test-user",
        "channel_id": "ABCDE33",
    }
    print(lambda_handler(event, {}))
