import os
import sys
import json
import urllib2

import push.log
import push.ssh
import push.args
import push.hosts
import push.config


def nasty_error(message, *args):
    full_message = "%s: %s" % (os.path.basename(sys.argv[0]),
                               str(message) % args)

    print push.log.colorize(full_message,
                            color=push.log.RED,
                            bold=True)


def _parse_args(config):
    parser = push.args.ArgumentParser(description="Collect deployed code revisions",
                                      add_help=False)
    parser.add_argument("-h", dest="host_refs", metavar="HOST", default=[],
                              action="append", nargs="+",
                              help="hosts or groups to collect data from",
                              required=True)
    parser.add_argument("--help", action="help", help="display this help")

    args = parser.parse_args()
    args.hosts = push.args.expand_host_refs(config, args.host_refs)
    args.testing = False

    return args


def get_revisions(hosts):
    report = {}

    for host in hosts:
        try:
            f = urllib2.urlopen("http://%s:8002/health" % host, timeout=3)
            host_data = json.load(f)
            f.close()
        except urllib2.URLError, e:
            nasty_error("%s: %s", host, e)
            continue

        if "r2" in host_data:
            host_data["public"] = host_data["r2"]
            del host_data["r2"]
        report[host] = host_data

    return report


def revisions():
    try:
        config = push.config.parse_config()
        args = _parse_args(config)
    except (push.config.ConfigurationError, push.args.ArgumentError,
            push.hosts.HostOrAliasError, push.hosts.HostLookupError), e:
        nasty_error(e)
        return 1

    # get the revisions from the remote hosts
    report = get_revisions(args.hosts)

    known_repos = set()
    for host, revisions in report.iteritems():
        known_repos.update(revisions.iterkeys())
    known_repos = sorted(known_repos)

    # ask the build host what the most recent revisions are
    ssh = push.ssh.SshDeployer(config, args, None)
    current_revisions = {}
    for repo in known_repos:
        revision = ssh.run_build_command("get-revision", repo,
                                         "origin/master",
                                         display_output=False)
        current_revisions[repo] = revision

    # tell the user
    print "host".ljust(14),
    print "".join(repo.rjust(14) for repo in known_repos)
    for host in args.hosts:
        print host.ljust(14) + "  ",

        for repo in known_repos:
            rev = report[host][repo]
            output = rev[:8].rjust(14)
            if rev != current_revisions[repo]:
                output = push.log.colorize(output,
                                           color=push.log.RED,
                                           bold=True)
            else:
                output = push.log.colorize(output,
                                           color=push.log.GREEN,
                                           bold=True)
            print output,

        print
