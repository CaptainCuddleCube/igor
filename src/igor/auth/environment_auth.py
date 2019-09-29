import os


class Auth:
    def __init__(self, token=None):
        self._app_token = os.environ["SLACK_TOKEN"]
        # self._access_groups = access_groups
        if token is not None:
            self.validate_token(token)
        else:
            raise ValueError("Invalid token")
        self._oauth_token = os.environ["OAUTH_TOKEN"]

    def validate_token(self, token):
        if token != self._app_token:
            raise ValueError("Access Denied")

    def staple_oath_token(self, data):
        data["token"] = self._oauth_token
        return data

    @property
    def auth_token(self):
        return self._oauth_token
