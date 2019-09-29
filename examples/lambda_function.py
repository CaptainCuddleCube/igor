import json
from igor import Igor
from igor import send_slack_message
from igor.plugins.contrib.aws import InstanceControl
from igor.auth.environment_auth import Auth

commands = {
    "list-instances": {
        "plugin": {"name": "AwsInstanceControl", "function": "instance_names"},
        "slack-alert": False,
    },
    "reboot": {
        "plugin": {"name": "AwsInstanceControl", "function": "reboot_instance"},
        "slack-alert": True,
    },
    "start": {
        "plugin": {"name": "AwsInstanceControl", "function": "start_instance"},
        "slack-alert": True,
    },
    "status": {
        "plugin": {"name": "AwsInstanceControl", "function": "instance_state"},
        "slack-alert": True,
    },
    "stop": {
        "plugin": {"name": "AwsInstanceControl", "function": "stop_instance"},
        "slack-alert": True,
    },
    "help": {"plugin": {"name": "igor", "function": "help"}, "slack-alert": False},
}


def lambda_handler(event, context):
    if event["command"] == "/igor":
        message = event["text"]
        user = event["user_name"]
        channel = event["channel_id"]
        token = event["token"]
        auth = Auth(token)
        plugins = {"AwsInstanceControl": InstanceControl(channel)}
        igor = Igor(plugins, commands)
        response = igor.do_this(message)
        if "public" in response:
            send_slack_message(
                auth.auth_token, user, channel, message, response["public"]
            )
        elif "private" in response:
            return response["private"]
    else:
        return f"Command {event['command']} is unknown"


if __name__ == "__main__":
    event = {
        "token": "test-token",
        "command": "/igor",
        "text": "help",
        "user_name": "test-user",
        "channel_id": "ABCDE33",
    }
    print(lambda_handler(event, {}))

    # event = {
    #     "token": "test-token",
    #     "command": "/igor",
    #     "text": "list-instances",
    #     "user_name": "test-user",
    #     "channel_id": "ABCDE33",
    # }
    # print(lambda_handler(event, {}))

    # event = {
    #     "token": "test-token",
    #     "command": "/igor",
    #     "text": "status Test-instance",
    #     "user_name": "test-user",
    #     "channel_id": "ABCDE33",
    # }
    # print(lambda_handler(event, {}))

    # event = {
    #     "token": "test-token",
    #     "command": "/igor",
    #     "text": "status --instance_name Test-instance",
    #     "user_name": "test-user",
    #     "channel_id": "ABCDE33",
    # }
    # print(lambda_handler(event, {}))
