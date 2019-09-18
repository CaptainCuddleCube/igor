import boto3
from botocore.exceptions import ClientError

from .exceptions import PluginError


def error_handler(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ClientError as error:
            if "DryRunOperation" in str(error):
                return "Dry run was successful"
            else:
                raise PluginError(
                    "An error with the client or the instance id has been detected"
                )
        except Exception as e:
            raise PluginError("An unkown error has occured, time to panic: " + str(e))

    return wrapper


class AwsFunctions:
    def __init__(self, channel):
        self._channel = channel

        self.schema = {
            "instance_names": {
                "required": [],
                "switches": [],
                "help": "Returns a list of the instance names your channel can see.",
            },
            "instance_id": {"required": ["instance_name"], "switches": []},
            "instance_state": {"required": ["instance_name"], "switches": ["dry_run"]},
            "start_instance": {"required": ["instance_name"], "switches": ["dry_run"]},
            "stop_instance": {
                "required": ["instance_name"],
                "switches": ["dry_run", "force"],
            },
            "reboot_instance": {"required": ["instance_name"], "switches": ["dry_run"]},
        }

    @error_handler
    def instance_names(self):
        client = boto3.client("ec2")
        response = client.describe_instances(
            Filters=[{"Name": f"tag:Channel_id", "Values": [self._channel]}]
        )
        instance_names = []
        for i in response["Reservations"]:
            if "Instances" in i:
                for j in i["Instances"]:
                    name = [tag["Value"] for tag in j["Tags"] if tag["Key"] == "Name"]
                    name = name.pop() if len(name) else ""
                    instance_names.append(name)
        return instance_names

    @error_handler
    def instance_id(self, instance_name):
        client = boto3.client("ec2")
        response = client.describe_instances(
            Filters=[
                {"Name": "tag:Channel_id", "Values": [self._channel]},
                {"Name": "tag:Name", "Values": [instance_name]},
            ]
        )
        for i in response["Reservations"]:
            if "Instances" in i:
                for j in i["Instances"]:
                    return j["InstanceId"]

    @error_handler
    def instance_state(self, instance_name: str, dry_run: bool = False) -> str:
        instance_id = self.instance_id(instance_name)
        client = boto3.client("ec2")
        response = client.describe_instance_status(
            InstanceIds=[instance_id], DryRun=dry_run
        )
        if len(response["InstanceStatuses"]) == 0:
            return "Instance state: stopped"
        else:
            return f'Instance state: {response["InstanceStatuses"][0]["InstanceState"]["Name"]}'

    @error_handler
    def start_instance(self, instance_name: str, dry_run: bool = False) -> str:
        instance_id = self.instance_id(instance_name)
        client = boto3.client("ec2")
        response = client.start_instances(InstanceIds=[instance_id], DryRun=dry_run)
        return self._format_state_change(
            response["StartingInstances"], response["StartingInstances"]
        )

    @error_handler
    def stop_instance(
        self, instance_name: str, dry_run: bool = False, force: bool = False
    ) -> str:
        instance_id = self.instance_id(instance_name)
        client = boto3.client("ec2")
        response = client.stop_instances(
            InstanceIds=[instance_id], DryRun=dry_run, Force=force
        )
        return self._format_state_change(
            response["StoppingInstances"], response["StoppingInstances"]
        )

    @error_handler
    def reboot_instance(self, instance_name: str, dry_run: bool = False) -> str:
        instance_id = self.instance_id(instance_name)
        client = boto3.client("ec2")
        client.reboot_instances(InstanceIds=[instance_id], DryRun=dry_run)
        return "Instance is rebooting"

    def _format_state_change(self, prev: str, curr: str) -> str:
        prev = prev[0]["PreviousState"]["Name"]
        curr = curr[0]["CurrentState"]["Name"]
        if prev == curr:
            return f"Instance state has not changed from: {curr}"
        else:
            return f"Instance changing: {prev} --> {curr}"
