"""Errors the user can fix (input video, room name, config, run folder).

The CLI prints only the message of a UserError; any other exception is a bug and keeps its
traceback.
"""


class UserError(Exception):
    pass
