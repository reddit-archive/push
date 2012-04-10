import re
import fnmatch
import dns.name
import dns.zone
import dns.query
import dns.exception
import dns.resolver
import dns.rdtypes


MAX_NESTED_ALIASES = 10


def sorted_nicely(iter):
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


def _get_hosts_from_dns(config):
    """Does a DNS zone transfer off the SOA for a given domain to get a list of
    hosts that can be pushed to."""

    try:
        soa_answer = dns.resolver.query(config.dns.domain, "SOA", tcp=True)
        master_answer = dns.resolver.query(soa_answer[0].mname, "A", tcp=True)
        xfr_answer = dns.query.xfr(master_answer[0].address, config.dns.domain)
        zone = dns.zone.from_xfr(xfr_answer)
        return sorted_nicely([name.to_text()
                              for name, ttl, rdata in
                              zone.iterate_rdatas("A")])
    except dns.exception.DNSException, e:
        raise HostLookupError("host lookup by dns failed: %r" % e)


class HostOrAliasError(Exception):
    def __init__(self, alias, fmt, *args):
        self.alias = alias
        self.fmt = fmt
        self.args = args

    def __str__(self):
        return ('alias "%s":' % self.alias) + " " + (self.fmt % self.args)


def get_hosts_and_aliases(config):
    """Fetches hosts from DNS then aliases them by globs specified in
    the config file. Returns a tuple of (all_hosts:list, aliases:dict)."""

    all_hosts = _get_hosts_from_dns(config)
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
