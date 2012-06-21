from __future__ import absolute_import

import syslog
import getpass


def register(config, args, deployer, log):
    def write_syslog(message):
        syslog.syslog(config.syslog.priority, message.encode('utf-8'))

    syslog.openlog(ident=config.syslog.ident, facility=config.syslog.facility)

    @deployer.push_began
    def on_push_began(deployer):
        user = getpass.getuser()
        write_syslog('Push %s started by '
                     '%s with args "%s"' % (args.push_id, user,
                                            args.command_line))

    @deployer.push_ended
    def on_push_ended(deployer):
        write_syslog("Push %s complete!" % args.push_id)

    @deployer.push_aborted
    def on_push_aborted(deployer, exception):
        write_syslog("Push %s aborted (%s)" % (args.push_id, exception))
