import boto3
from botocore.exceptions import ClientError
from typing import List, Dict


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
                return "A client error has been detected"
        except Exception as e:
            print(e)
            return "An error has occured, time to panic"

    return wrapper


class InstanceGroups:
    def __init__(self, instances):
        self._instances = instances

    def get_group(self, group_name):
        return self._instances.get(group_name, [])


class Authorization:
    def __init__(self, token, channel, user, access_groups):
        if token != "test-token":
            raise ValueError("Access Denied")
        if not set([channel, user]) & set(access_groups):
            raise ValueError("Access Denied")

        self._channel_resources = access_groups.get(channel, "")
        self._user_resources = access_groups.get(user, "")

    def get_resource_groups(self):
        return [self._channel_resources, self._user_resources]


class Igor:
    def __init__(self, token, channel, user, access_groups, instances):
        self._auth = Authorization(token, channel, user, access_groups)
        self._instance_groups = InstanceGroups(instances)
        dry_run = {"dry-run": "dry_run"}
        force = {"force": "force"}
        self._commands = {
            "list-instances": {"sub-commands": {}, "exec": self._list_instances},
            "reboot": {"sub-commands": dry_run, "exec": self._reboot_instance},
            "start": {"sub-commands": dry_run, "exec": self._start_instance},
            "status": {"sub-commands": dry_run, "exec": self._instance_state},
            "stop": {"sub-commands": {**dry_run, **force}, "exec": self._stop_instance},
        }

    def do_this(self, message: str) -> str:
        instruction = message.split()
        command = self._parse_command(instruction[0])
        instance_id = self._get_instance_id(instruction[1])
        kwargs = self._get_kwarg_subcommands(command, instruction[2:])
        kwargs = {**kwargs, "instance_id": instance_id}
        return self._run_command(command, **kwargs)

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
        resource_groups = self._auth.get_resource_groups()
        resources = []
        for group_name in resource_groups:
            for resource in self._instance_groups.get_group(group_name):
                resources.append(resource)
        return resources

    def _get_instance_id(self, instance_name: str) -> str:
        instance_id = {
            i["id"] for i in self._get_resources() if instance_name == i["name"]
        }
        if len(instance_id) == 0:
            return ""

        return list(instance_id)[0]

    def _list_instances(self, **kwargs) -> str:
        return ", ".join([f'"{i["name"]}"' for i in self._get_resources()])

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


def lambda_handler(event: dict, context: dict) -> str:
    message = event["event"]["text"] if event["event"]["type"] == "message" else ""
    user = event["event"]["user"]
    channel = event["event"]["channel"]
    token = event["token"]

    # This is configuration that can be used.
    instance_groups = {
        "instance": [{"id": "i-0fa3dde55b3ba0", "name": "test-instance"}]
    }
    access_groups = {"channel1": "instance"}

    igor = Igor(token, channel, user, access_groups, instance_groups)
    result = igor.do_this(message)
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
