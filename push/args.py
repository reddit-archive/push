import sys
import argparse
import collections

import push.hosts


__all__ = ["parse_args", "ArgumentError"]


class MutatingAction(argparse.Action):
    def __init__(self, *args, **kwargs):
        self.type_to_mutate = kwargs.pop("type_to_mutate")
        argparse.Action.__init__(self, *args, **kwargs)

    def get_attr_to_mutate(self, namespace):
        o = getattr(namespace, self.dest, None)
        if not o:
            o = self.type_to_mutate()
            setattr(namespace, self.dest, o)
        return o


class SetAddConst(MutatingAction):
    "Action that adds a constant to a set."
    def __init__(self, *args, **kwargs):
        kwargs["nargs"] = 0
        MutatingAction.__init__(self, *args, type_to_mutate=set, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        s = self.get_attr_to_mutate(namespace)

        if hasattr(self.const, "__iter__"):
            for x in self.const:
                s.add(x)
        else:
            s.add(self.const)


class SetAddValues(MutatingAction):
    "Action that adds values to a set."
    def __init__(self, *args, **kwargs):
        MutatingAction.__init__(self, *args, type_to_mutate=set, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        s = self.get_attr_to_mutate(namespace)

        for x in values:
            s.add(x)


class DictAdd(MutatingAction):
    "Action that adds an argument to a dict with a constant key."
    def __init__(self, *args, **kwargs):
        MutatingAction.__init__(self, *args, type_to_mutate=dict, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        d = self.get_attr_to_mutate(namespace)
        key, value = values
        d[key] = value


class RestartCommand(MutatingAction):
    """Makes a deploy command out of -r (graceful restart) options."""

    def __init__(self, *args, **kwargs):
        MutatingAction.__init__(self, *args, type_to_mutate=list, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        command_list = self.get_attr_to_mutate(namespace)
        command_list.append(["restart", values[0]])


class KillCommand(MutatingAction):
    """Makes a deploy command out of -k (kill) options."""

    def __init__(self, *args, **kwargs):
        MutatingAction.__init__(self, *args, type_to_mutate=list, **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        command_list = self.get_attr_to_mutate(namespace)
        command_list.append(["kill", values[0]])


class StoreIfHost(argparse.Action):
    "Stores value if it is a known host."
    def __init__(self, *args, **kwargs):
        self.all_hosts = kwargs.pop("all_hosts")
        argparse.Action.__init__(self, *args, **kwargs)

    def __call__(self, parser, namespace, value, option_string=None):
        if value not in self.all_hosts:
            raise argparse.ArgumentError(self, 'unknown host "%s"' % value)
        setattr(namespace, self.dest, value)


class ArgumentError(Exception):
    "Exception raised when there's something wrong with the arguments."
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class ArgumentParser(argparse.ArgumentParser):
    """Custom argument parser that raises an exception rather than exiting
    the program"""

    def error(self, message):
        raise ArgumentError(message)


def _parse_args():
    parser = ArgumentParser(description="Deploy stuff to servers.",
                            epilog="To deploy all code: push -h apps "
                                   "-pc -dc -r all",
                            add_help=False)

    parser.add_argument("-h", dest="host_refs", metavar="HOST", required=True,
                        action="append", nargs="+",
                        help="hosts or groups to execute commands on")
    parser.add_argument("--sleeptime", dest="sleeptime", nargs="?",
                        type=int, default=5,
                        metavar="SECONDS",
                        help="time in seconds to sleep between hosts")

    flags_group = parser.add_argument_group("flags")
    flags_group.add_argument("-t", dest="testing", action="store_true",
                             help="testing: print but don't execute")
    flags_group.add_argument("-q", dest="quiet", action="store_true",
                             help="quiet: no output except errors. implies "
                                  "--no-input")
    flags_group.add_argument("--no-irc", dest="notify_irc",
                             action="store_false",
                             help="don't announce actions in irc")
    flags_group.add_argument("--no-static", dest="build_static",
                             action="store_false",
                             help="don't build static files")
    flags_group.add_argument("--no-input", dest="auto_continue",
                             action="store_true",
                             help="don't wait for input after deploy")

    startat_shuffle = parser.add_mutually_exclusive_group()
    startat_shuffle.add_argument("--startat", dest="start_at",
                                 action="store", nargs='?',
                                 help="skip to this position in the host list")
    startat_shuffle.add_argument("--shuffle", dest="shuffle",
                                 action="store_true", help="shuffle host list")

    parser.add_argument("--help", action="help", help="display this help")

    deploy_group = parser.add_argument_group("deploy")
    deploy_group.add_argument("-p", dest="fetches",
                              action=SetAddValues, nargs="+",
                              metavar="REPO",
                              help="git-fetch the specified repo(s)")
    deploy_group.add_argument("-pc", dest="fetches", default=set(),
                              action=SetAddConst, const=["public", "private"],
                              help="short for -p public private")
    deploy_group.add_argument("-ppr", dest="fetches", default=set(),
                              action=SetAddConst, const=["private"],
                              help="short for -p private")

    deploy_group.add_argument("-d", dest="deploys",
                              action=SetAddValues, nargs="+",
                              metavar="REPO",
                              help="deploy the specified repo(s)")
    deploy_group.add_argument("-dc", dest="deploys", default=set(),
                              action=SetAddConst, const=["public", "private"],
                              help="short for -d public private")
    deploy_group.add_argument("-dpr", dest="deploys", default=set(),
                              action=SetAddConst, const=["private"],
                              help="short for -d private")
    deploy_group.add_argument("-rev", dest="revisions", default={},
                              metavar=("REPO", "REF"), action=DictAdd,
                              nargs=2,
                              help="revision to deploy for specified repo")

    parser.add_argument("-c", dest="deploy_commands", nargs="+",
                        metavar=("COMMAND", "ARG"), action="append",
                        help="deploy command to run on the host",
                        default=[])
    parser.add_argument("-r", dest="deploy_commands", nargs=1,
                        metavar="COMMAND", action=RestartCommand,
                        help="whom to (gracefully) restart on the host")
    parser.add_argument("-k", dest="deploy_commands", nargs=1,
                        action=KillCommand, choices=["all", "apps"],
                        help="whom to kill on the host")

    if len(sys.argv) == 1:
        parser.print_help()

    return parser.parse_args()


def parse_args(config):
    args = _parse_args()

    # quiet implies autocontinue
    if args.quiet:
        args.auto_continue = True

    # dereference the host lists
    all_hosts, aliases = push.hosts.get_hosts_and_aliases(config)
    args.hosts = []
    queue = collections.deque(args.host_refs)
    while queue:
        host_or_alias = queue.popleft()

        # individual instances of -h append a list to the list. flatten
        if hasattr(host_or_alias, "__iter__"):
            queue.extend(host_or_alias)
            continue

        # backwards compatibility with perl version
        if " " in host_or_alias:
            queue.extend(x.strip() for x in host_or_alias.split())
            continue

        if host_or_alias in all_hosts:
            args.hosts.append(host_or_alias)
        elif host_or_alias in aliases:
            args.hosts.extend(aliases[host_or_alias])
        else:
            raise ArgumentError('-h: unknown host or alias "%s"' %
                                host_or_alias)

    # make sure the startat is in the dereferenced host list
    if args.start_at and args.start_at not in args.hosts:
        raise ArgumentError('--startat: host "%s" not in host list.' %
                            args.start_at)

    return args
