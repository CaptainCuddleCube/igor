import boto3
from botocore.exceptions import ClientError

from plugins.exceptions import PluginError


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


class InstanceControl:
    def __init__(self, channel):
        self._channel = channel

        self.schema = {
            "instance_names": {
                "required": [],
                "switches": [],
                "help": "Returns a list of values of the Name tag for each instance that has has the Channel tag match your slack channel.",
            },
            "instance_id": {
                "required": ["instance_name"],
                "switches": [],
                "help": "Returns an instance id when given the instance's tag Name.",
            },
            "instance_state": {
                "required": ["instance_name"],
                "switches": ["dry_run"],
                "help": "Returns the state with the matching Name tag.",
            },
            "start_instance": {
                "required": ["instance_name"],
                "switches": ["dry_run"],
                "help": "For a given instance name, this command will ensure the instance is running. It can be run on a running instance.",
            },
            "stop_instance": {
                "required": ["instance_name"],
                "switches": ["dry_run", "force"],
                "help": "This will shut down the instance when given an instance name.",
            },
            "reboot_instance": {
                "required": ["instance_name"],
                "switches": ["dry_run"],
                "help": "This will restart an instance.",
            },
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
