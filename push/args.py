import sys
import argparse
import itertools
import collections

import push.hosts
import push.utils


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
        MutatingAction.__init__(self, *args,
                                type_to_mutate=collections.OrderedDict,
                                **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        s = self.get_attr_to_mutate(namespace)

        if hasattr(self.const, "__iter__"):
            for x in self.const:
                s[x] = ""
        else:
            s[self.const] = ""


class SetAddValues(MutatingAction):
    "Action that adds values to a set."
    def __init__(self, *args, **kwargs):
        MutatingAction.__init__(self, *args,
                                type_to_mutate=collections.OrderedDict,
                                **kwargs)

    def __call__(self, parser, namespace, values, option_string=None):
        s = self.get_attr_to_mutate(namespace)

        for x in values:
            s[x] = ""


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


def _parse_args(config):
    parser = ArgumentParser(description="Deploy stuff to servers.",
                            epilog="To deploy all code: push -h apps "
                                   "-pc -dc -r all",
                            add_help=False)

    parser.add_argument("-h", dest="host_refs", metavar="HOST", required=True,
                        action="append", nargs="+",
                        help="hosts or groups to execute commands on")
    parser.add_argument("--sleeptime", dest="sleeptime", nargs="?",
                        type=int, default=config.defaults.sleeptime,
                        metavar="SECONDS",
                        help="time in seconds to sleep between hosts")
    parser.add_argument("--startat", dest="start_at",
                        action="store", nargs='?', metavar="HOST",
                        help="skip to this position in the host list")
    parser.add_argument("--stopbefore", dest="stop_before",
                        action="store", nargs="?", metavar="HOST",
                        help="end the push on the host before this one")
    parser.add_argument("--pauseafter", dest="hosts_before_pause", nargs="?",
                        type=int, metavar="NUMBER", default=1,
                        help="push to NUMBER hosts before pausing")
    parser.add_argument("--seed", dest="seed", action="store",
                        nargs="?", metavar="WORD", default=None,
                        help="name of push to copy the shuffle-order of")
    parser.add_argument("--shuffle", dest="shuffle",
                        default=config.defaults.shuffle,
                        action="store_true", help="shuffle host list")
    parser.add_argument("--no-shuffle", dest="shuffle",
                        action="store_false",
                        help="don't shuffle host list")
    parser.add_argument("--list", dest="list_hosts",
                        action="store_true", default=False,
                        help="print the host list to stdout and exit")

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

    parser.add_argument("--help", action="help", help="display this help")

    deploy_group = parser.add_argument_group("deploy")
    deploy_group.add_argument("-p", dest="fetches", default=set(),
                              action=SetAddValues, nargs="+",
                              metavar="REPO",
                              help="git-fetch the specified repo(s)")
    deploy_group.add_argument("-pc", dest="fetches",
                              action=SetAddConst, const=["public", "private"],
                              help="short for -p public private")
    deploy_group.add_argument("-ppr", dest="fetches",
                              action=SetAddConst, const=["private"],
                              help="short for -p private")

    deploy_group.add_argument("-d", dest="deploys", default=set(),
                              action=SetAddValues, nargs="+",
                              metavar="REPO",
                              help="deploy the specified repo(s)")
    deploy_group.add_argument("-dc", dest="deploys",
                              action=SetAddConst, const=["public", "private"],
                              help="short for -d public private")
    deploy_group.add_argument("-dpr", dest="deploys",
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


def build_command_line(config, args):
    "Given a configured environment, build a canonical command line for it."
    components = []

    components.append("-h")
    components.extend(itertools.chain.from_iterable(args.host_refs))

    if args.start_at:
        components.append("--startat=%s" % args.start_at)

    if args.stop_before:
        components.append("--stopbefore=%s" % args.stop_before)

    if args.hosts_before_pause > 1:
        components.append("--pauseafter=%s" % args.hosts_before_pause)

    if args.fetches:
        components.append("-p")
        components.extend(args.fetches)

    if args.deploys:
        components.append("-d")
        components.extend(args.deploys)

    commands = dict(restart="-r",
                    kill="-k")
    for command in args.deploy_commands:
        special_command = commands.get(command[0])
        if special_command:
            components.append(special_command)
            command = command[1:]
        else:
            components.append("-c")

        components.extend(command)

    for repo, rev in args.revisions.iteritems():
        components.extend(("-rev", repo, rev))

    if not args.build_static:
        components.append("--no-static")

    if args.auto_continue:
        components.append("--no-input")

    if not args.notify_irc:
        components.append("--no-irc")

    if args.quiet:
        components.append("--quiet")

    if args.testing:
        components.append("-t")

    if args.shuffle:
        components.append("--shuffle")

    if args.seed:
        components.append("--seed=%s" % args.seed)

    components.append("--sleeptime=%d" % args.sleeptime)

    return " ".join(components)


def parse_args(config, host_source):
    args = _parse_args(config)

    # give the push a unique name
    args.push_id = push.utils.get_random_word(config)

    # quiet implies autocontinue
    if args.quiet or args.auto_continue:
        args.hosts_before_pause = 0

    # dereference the host lists
    all_hosts, aliases = push.hosts.get_hosts_and_aliases(config, host_source)
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

    # it really doesn't make sense to start-at while shufflin' w/o a seed
    if args.start_at and args.shuffle and not args.seed:
        raise ArgumentError("--startat: doesn't make sense "
                            "while shuffling without a seed")

    # make sure the stopbefore is in the dereferenced host list
    if args.stop_before and args.stop_before not in args.hosts:
        raise ArgumentError('--stopbefore: host "%s" not in host list.' %
                            args.stop_before)

    # it really doesn't make sense to stop-at while shufflin' w/o a seed
    if args.stop_before and args.shuffle and not args.seed:
        raise ArgumentError("--stopbefore: doesn't make sense "
                            "while shuffling without a seed")

    # restrict the host list if start_at or stop_before were defined
    if args.start_at or args.stop_before:
        if args.stop_before:
            args.hosts = itertools.takewhile(
                lambda host: host != args.stop_before, args.hosts)
        if args.start_at:
            args.hosts = itertools.dropwhile(
                lambda host: host != args.start_at, args.hosts)
        args.hosts = list(args.hosts)

    # do the shuffle!
    if args.shuffle:
        seed = args.seed or args.push_id
        push.utils.seeded_shuffle(seed, args.hosts)

    # build a psuedo-commandline out of args and defaults
    args.command_line = build_command_line(config, args)

    return args
