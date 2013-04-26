import sys
import os.path

import push.config
import push.args
import push.log
import push.deploy
import push.syslog
import push.irc
import push.cli


def main():
    host_source = None

    try:
        # read in the various configs and arguments and get ready
        try:
            config = push.config.parse_config()
            host_source = push.hosts.make_host_source(config)
            args = push.args.parse_args(config, host_source)

            if args.list_hosts:
                for host in args.hosts:
                    print host
                return 0

            log = push.log.Log(config, args)
        except (push.config.ConfigurationError, push.args.ArgumentError,
                push.hosts.HostOrAliasError, push.hosts.HostLookupError), e:
            print >> sys.stderr, "%s: %s" % (os.path.basename(sys.argv[0]), e)
            return 1
        else:
            deployer = push.deploy.Deployer(config, args, log, host_source)

        # set up listeners
        push.log.register(config, args, deployer, log)
        push.syslog.register(config, args, deployer, log)
        push.irc.register(config, args, deployer, log)
        push.cli.register(config, args, deployer, log)

        # go
        try:
            deployer.push()
        except push.deploy.PushAborted:
            pass
        except Exception, e:
            log.critical("Push failed: %s", e)
            return 1
        finally:
            log.close()

        return 0
    finally:
        if host_source:
            host_source.shut_down()

if __name__ == "__main__":
    sys.exit(main())
