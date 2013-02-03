import fnmatch
import importlib
import re


MAX_NESTED_ALIASES = 10


def _sorted_nicely(iter):
    """Sorts strings with embedded numbers in them the way humans would expect.

    http://nedbatchelder.com/blog/200712/human_sorting.html#comments"""

    def tryint(s):
        try:
            return int(s)
        except ValueError:
            return s

    def alphanum_key(s):
        return [tryint(c) for c in re.split('([0-9]+)', s)]

    return sorted(iter, key=alphanum_key)


class HostLookupError(Exception):
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class HostOrAliasError(Exception):
    def __init__(self, alias, fmt, *args):
        self.alias = alias
        self.fmt = fmt
        self.args = args

    def __str__(self):
        return ('alias "%s":' % self.alias) + " " + (self.fmt % self.args)


class HostSource(object):
    def get_all_hosts(self):
        raise NotImplementedError


def make_host_source(config):
    source_name = config.hosts.source
    source_module = importlib.import_module("push.hosts." + source_name)
    source_cls = getattr(source_module, source_name.title() + "HostSource")
    return source_cls(config)


def get_hosts_and_aliases(config, host_source):
    """Fetches hosts from DNS then aliases them by globs specified in
    the config file. Returns a tuple of (all_hosts:list, aliases:dict)."""

    all_hosts = _sorted_nicely(host_source.get_all_hosts())
    aliases = {}

    def dereference_alias(alias_name, globs, depth=0):
        if depth > MAX_NESTED_ALIASES:
            raise HostOrAliasError(alias_name,
                             "exceeded maximum recursion depth. "
                             "circular reference?")

        hosts = []
        for glob in globs:
            if glob.startswith("@"):
                # recursive alias reference
                subalias_name = glob[1:]
                if subalias_name not in config.aliases:
                    raise HostOrAliasError(alias_name,
                                     'referenced undefined alias "%s"',
                                     subalias_name)
                subhosts = dereference_alias(subalias_name,
                                             config.aliases[subalias_name],
                                             depth=depth + 1)
                hosts.extend(subhosts)
            else:
                globbed = fnmatch.filter(all_hosts, glob)
                if not globbed:
                    raise HostOrAliasError(alias_name, 'unmatched glob "%s"',
                                           glob)
                hosts.extend(globbed)
        return hosts

    for alias, globs in config.aliases.iteritems():
        aliases[alias] = dereference_alias(alias, globs)

    return all_hosts, aliases
