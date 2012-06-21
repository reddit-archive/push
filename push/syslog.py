from __future__ import absolute_import

import syslog
import getpass
import functools


def register(config, args, deployer, log):
    write_syslog = functools.partial(syslog.syslog, config.syslog.priority)

    syslog.openlog(ident=config.syslog.ident, facility=config.syslog.facility)

    @deployer.push_began
    def on_push_began(deployer):
        user = getpass.getuser()
        write_syslog('Push %s started by '
                     '%s with args "%s"' % (log.push_id, user,
                                            args.command_line))

    @deployer.push_ended
    def on_push_ended(deployer):
        write_syslog("Push %s complete!" % log.push_id)

    @deployer.push_aborted
    def on_push_aborted(deployer, exception):
        write_syslog("Push %s aborted (%s)" % (log.push_id, exception))
