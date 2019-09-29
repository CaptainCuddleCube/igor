import requests


def send_slack_message(auth_token, user, channel, user_message, command_response):
    message = f"""{user} told igor to "{user_message}".\n{command_response}"""
    data = dict(channel=channel, pretty=1, text=message, token=auth_token)
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
    }
    requests.post("https://slack.com/api/chat.postMessage", data=data, headers=headers)
