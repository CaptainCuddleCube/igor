import shlex
import requests
from random import uniform
from plugins.exceptions import PluginError


class Igor:
    def __init__(self, channel, user_name, auth, plugins, commands):
        self._auth = auth
        self.channel = channel
        self.user = user_name
        self._plugins = {**plugins, **{"igor": self}}

        self._peon_quotes = [
            "No time for play.",
            "Me not that kind of orc!",
            "Okie dokie.",
            "Work, work.",
            "Why you poking me again?",
            "Froedrick!",
            "I've got no body, nobody's got me. Hachachacha.",
        ]

        self.commands = commands

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

    def _parse_value_pairs(self, unordered_pairs):
        pairs = {}
        key = None
        next_is_paired = False
        for i in unordered_pairs:
            if i.startswith("--"):
                next_is_paired = True
                key = i.replace("--", "")
            elif next_is_paired:
                pairs[key] = i
                next_is_paired = False
                key = None
        return pairs

    def _gather_requirements(
        self, pairs: dict, command: str, plugin_params: list
    ) -> dict:
        """
        A function that will keep looking for dependencies required to 
        fulfill a request.
        """
        data = {}
        missing_params = [i for i in plugin_params if i not in pairs]
        for i in missing_params:
            plugin = self._plugins[self.commands[command]["plugin"]["name"]]
            reqs = plugin.schema[i]["required"]
            needed = [i for i in reqs if i not in pairs]
            pairs = self._gather_requirements(
                pairs=pairs, command=command, plugin_params=needed
            )
            func = getattr(plugin, i)
            req = {k: pairs[k] for k in reqs}
            data = {**data, **{i: func(**req)}}

        return {**data, **pairs}

    def _get_switches(self, function_switches, instruction):
        kwargs = {}
        for switch in function_switches:
            if "--" + switch in instruction:
                kwargs[switch] = True
        return kwargs

    def _extract_required_args(self, function_requirements, instruction):
        args = []
        # Getting the oridinal values.
        for i in instruction:
            if i.startswith("--"):
                break
            else:
                args.append(i)
                function_requirements = function_requirements[1:]
                instruction = instruction[1:]

        return (args, instruction, function_requirements)

    def _extract_required_kwargs(self, function_requirements, instruction):
        kwargs = {}
        for req in function_requirements:
            if "--" + req in instruction:
                index = instruction.index("--" + req)
                if index == len(instruction) - 1:
                    raise ValueError("Invalid command")
                kwargs[req] = instruction[+1]
                function_requirements = function_requirements[1:]
                instruction = instruction[:index] + instruction[index + 2 :]

        return (kwargs, instruction, function_requirements)

    def _get_parameters(self, requirements, function_switches, instruction):
        args, instruction, requirements = self._extract_required_args(
            requirements, instruction
        )
        kwargs, instruction, requirements = self._extract_required_kwargs(
            requirements, instruction
        )
        assert (
            len(requirements) == 0
        ), f"The requirments: {requirements} have not been met"

        # Extract the switches.
        kwargs = {**kwargs, **self._get_switches(function_switches, instruction)}

        return args, kwargs

    def _get_plugin(self, command):
        plugin_name = self.commands[command]["plugin"]["name"]
        return self._plugins[plugin_name]

    def do_this(self, message: str) -> str:
        instruction = shlex.split(message)
        root_command = self._parse_command(instruction[0])

        instruction = instruction[1:]
        plugin = self._get_plugin(root_command)
        function = self.commands[root_command]["plugin"]["function"]

        # we need to get the schema information:
        schema = self._get_plugin_schema(root_command)
        function_reqs = schema.get("required", [])
        function_switches = schema.get("switches", [])
        # Getting the args and kwargs used for this parameter.
        args, kwargs = self._get_parameters(
            function_reqs, function_switches, instruction
        )

        try:
            response = getattr(plugin, function)(*args, **kwargs)
            if self.commands[root_command]["slack-alert"]:
                self.send_slack_message(message, response)
                print(response)
                return self._peon_quotes[int(uniform(0, len(self._peon_quotes)))]
            else:
                return response
        except PluginError as e:
            plugin_name = self.commands[root_command]["plugin"]["name"]
            return f"Error with plugin {plugin_name}: " + str(e)
        except Exception as e:
            return "Error: " + str(e)

    def help(self):
        msg = "Igor is your friendly worker that helps control things for you!\n\n"
        msg += "The currently supported commands are:\n\n"
        for i in self.commands:
            msg += f"{i}"
            if "help" in self._get_plugin_schema(i):
                msg += ": " + self._get_plugin_schema(i)["help"]
            msg += "\n"
        return msg

    def _get_plugin_schema(self, command):
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

    def _parse_command(self, command: str) -> str:
        if command not in self.commands:
            raise ValueError("Invalid command")
        return command
