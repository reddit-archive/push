import sys
import tty
import time
import termios
import signal

import push.deploy


SIGNAL_MESSAGES = {signal.SIGINT: "received SIGINT",
                   signal.SIGHUP: "received SIGHUP. tsk tsk."}


def read_character():
    "Read a single character from the terminal without echoing it."
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setcbreak(fd)
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def wait_for_input(log, deployer):
    """Wait for the user's choice of whether or not to continue the push.
    Return whether or not to auto-continue after further hosts."""

    print >> log, ('Press "x" to abort, "c" to go to the next host, or '
                   '"a" to continue automatically.')

    while True:
        c = read_character()
        if c == "a":
            print >> log, "Continuing automatically. Press ^C to abort."
            return True
        elif c == "x":
            deployer.cancel_push('"x" pressed')
        elif c == "c":
            return False


def sleep_with_countdown(log, sleeptime):
    if sleeptime == 0:
        return

    print >> log, "Sleeping...",
    log.flush()

    for i in xrange(sleeptime, 0, -1):
        print >> log, " %d..." % i,
        log.flush()
        time.sleep(1)

    print >> log, ""


def register(config, args, deployer, log):
    def sighandler(sig, stack):
        reason = SIGNAL_MESSAGES[sig]
        deployer.cancel_push(reason)

    @deployer.push_began
    def on_push_began(deployer):
        signal.signal(signal.SIGINT, sighandler)
        signal.signal(signal.SIGHUP, sighandler)

        if args.testing:
            log.warning("*** Testing mode. No commands will be run. ***")

        log.notice("*** Beginning push. ***")
        log.notice("Log available at %s", log.log_path)

    @deployer.synchronize_began
    def on_sync_began(deployer):
        log.notice("Synchronizing build repos with GitHub...")

    @deployer.resolve_refs_began
    def on_resolve_refs_began(deployer):
        log.notice("Resolving refs...")

    @deployer.deploy_to_build_host_began
    def on_deploy_to_build_host_began(deployer):
        log.notice("Deploying to build host...")

    @deployer.build_static_began
    def on_build_static_began(deployer):
        log.notice("Building static files...")

    @deployer.process_host_began
    def on_process_host_began(deployer, host):
        log.notice('Starting host "%s"...', host)

    @deployer.process_host_ended
    def on_process_host_ended(deployer, host):
        host_index = args.hosts.index(host) + 1
        host_count = len(args.hosts)
        percentage = int((float(host_index) / host_count) * 100)
        log.notice('Host "%s" done (%d of %d -- %d%% done).',
                   host, host_index, host_count, percentage)

        if args.hosts[-1] == host:
            pass
        elif args.auto_continue:
            sleep_with_countdown(log, args.sleeptime)
        else:
            args.auto_continue = wait_for_input(log, deployer)

    @deployer.push_ended
    def on_push_ended(deployer):
        log.notice("*** Push complete! ***")

    @deployer.push_aborted
    def on_push_aborted(deployer, exception):
        if isinstance(exception, push.deploy.PushAborted):
            log.critical("\n*** Push cancelled (%s) ***", exception)
