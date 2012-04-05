import sys
import wessex
import getpass
import datetime


def register(config, args, deployer, log):
    if not args.notify_irc:
        return

    harold = wessex.Harold(host=config.harold.host,
                           secret=config.harold.secret,
                           port=config.harold.port,
                           timeout=config.harold.timeout)
    channel = harold.get_irc_channel(config.harold.channel)

    def log_exception_and_continue(fn):
        def wrapper(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except Exception, e:
                log.warning("Harold error: %s", e)
        return wrapper

    @deployer.push_began
    @log_exception_and_continue
    def on_push_began(deployer):
        user = getpass.getuser()
        time = datetime.datetime.now().strftime("%H:%M")
        args = " ".join(sys.argv[1:])

        channel.set_topic('Push started by %s at %s '
                          'with args: %s' % (user, time, args))
        channel.message('%s started push with arguments: %s. '
                        'Log in %s' % (user, args, log.log_path))

    @deployer.process_host_ended
    @log_exception_and_continue
    def on_process_host_ended(deployer, host):
        num_hosts = len(args.hosts)
        if num_hosts <= 4:
            return

        quadrant = getattr(deployer, "quadrant", 1)
        host_index = args.hosts.index(host) + 1
        percentage = float(host_index) / num_hosts

        if percentage > int(quadrant * .25):
            channel.message("Push %d%% complete." % (25 * quadrant))
            deployer.quadrant = quadrant + 1

    @deployer.push_ended
    @log_exception_and_continue
    def on_push_ended(deployer):
        channel.message('Push complete!')
        channel.restore_topic()

    @deployer.push_aborted
    @log_exception_and_continue
    def on_push_aborted(deployer, e):
        channel.message('Push aborted (%s)' % e)
        channel.restore_topic()
