import boto3
from botocore.exceptions import ClientError
from typing import List, Dict

# A simple slack bot that allows a user easy access to start, stop, reboot and check the status of
# an instance. The slack bot works by asking is simple questions. There are 5 stats currently:
# get-instances, reboot, start, state, stop.
# /igor get-instances
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


# The grouping of instances that can be controlled
INSTANCES = {"instance": [{"id": "i-0aa3dde55b34a0fbd", "name": "test-instance"}]}

# The users or channels that can access things.
AUTHORIZED_USERS = {"channel1": INSTANCES["instance"]}

TOKEN = "test-token"


def error_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ClientError as error:
            if "DryRunOperation" in str(error):
                return "Dry run is successful"
            else:
                return "A client error has been detected"
        except Exception as e:
            print(e)
            return "An error has occured, time to panic"

    return wrapper


def format_state_change(prev: str, curr: str) -> str:
    if prev == curr:
        return f"Instance state has not changed from: {curr}"
    else:
        return f"Changing instande state: {prev} --> {curr}"


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


@error_handler
def start_instance(instance_id: str, dry_run: bool = False) -> str:
    client = boto3.client("ec2")
    response = client.start_instances(InstanceIds=[instance_id], DryRun=dry_run)
    return format_state_change(
        response["StartingInstances"][0]["PreviousState"]["Name"],
        response["StartingInstances"][0]["CurrentState"]["Name"],
    )


@error_handler
def stop_instance(instance_id: str, dry_run: bool = False, force: bool = False) -> str:
    client = boto3.client("ec2")
    response = client.stop_instances(
        InstanceIds=[instance_id], DryRun=dry_run, Force=force
    )
    return format_state_change(
        response["StoppingInstances"][0]["PreviousState"]["Name"],
        response["StoppingInstances"][0]["CurrentState"]["Name"],
    )


@error_handler
def reboot_instance(instance_id: str, dry_run: bool = False) -> str:
    client = boto3.client("ec2")
    client.reboot_instances(InstanceIds=[instance_id], DryRun=dry_run)
    return "Instance is rebooting"


def list_instances(instances: List) -> str:
    return ", ".join([f'"{i["name"]}"' for i in instances])


def get_instance_id(instance_name: str, channel: str, user: str) -> str:
    instance_id = {
        i["id"]
        for i in [*AUTHORIZED_USERS.get(channel,[]), *AUTHORIZED_USERS.get(user,[])]
        if instance_name == i["name"]
    }
    if len(instance_id) == 0:
        raise ValueError("Invalid instance name")

    return list(instance_id)[0]


def get_kwarg_subcommands(command, possible_subcommands: List) -> Dict:
    subcommands = VALID_REQUESTS[command]["sub-commands"]
    # filter for commands that are valid and inject our own valid value.
    return {
        subcommands[i]: True for i in list(set(possible_subcommands) & set(subcommands))
    }


def valide_command(command: str) -> str:
    if command not in VALID_REQUESTS:
        raise ValueError("Invalid command")
    return command


# This valid requests that are checked before anything is run
VALID_REQUESTS = {
    "reboot": {"sub-commands": {"dry-run": "dry_run"}, "function": reboot_instance},
    "start": {"sub-commands": {"dry-run": "dry_run"}, "function": start_instance},
    "state": {"sub-commands": {"dry-run": "dry_run"}, "function": instance_state},
    "stop": {
        "sub-commands": {"dry-run": "dry_run", "force": "force"},
        "function": stop_instance,
    },
}


def lambda_handler(event: dict, context: dict) -> str:
    message = event["event"]["text"] if event["event"]["type"] == "message" else ""
    user = event["event"]["user"]
    channel = event["event"]["channel"]
    token = event["token"]

    if token != TOKEN:
        raise ValueError("Token not valid")

    # Split on white space
    instruction = message.split()
    command = valide_command(instruction[0])

    # Process the instance name by looking through auhtorized users.
    instance_id = get_instance_id(instruction[1], channel, user)

    # Get the kwarg subcommands that can be passed into the command's function
    kwarg_subcommands = get_kwarg_subcommands(command, instruction[2:])

    # Call the function registered to this command
    result = VALID_REQUESTS[command]["function"](
        instance_id, **kwarg_subcommands
    )
    return result


if __name__ == "__main__":
    event = {
        "token": "test-token",
        "event": {
            "type": "message",
            "text": "state test-instance",
            "user": "test",
            "channel": "channel1",
            "token": "test-token",
        },
    }

    print(lambda_handler(event, {}))
