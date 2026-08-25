"""The one refusal type the operator CLI raises."""


class OpsError(Exception):
    """A refusal the operator can act on.

    Every message is written for the person at the terminal and names the way
    forward where one exists ("use ``user enrol``", "run ``user resync``
    first"). :func:`policy_atlas.ops.cli.main` catches it, prints it to stderr
    and exits non-zero; nothing else in the package raises it for control flow.

    The distinction that matters: an :class:`OpsError` means *nothing was
    written*, except where the message says otherwise — ``user create``'s
    database-failure path is the single exception, and it says so in the text
    because the Cognito account it kept is real.
    """
