import wessex
import getpass


def register(config, args, deployer, log):
    if not args.notify_irc:
        return

    harold = wessex.connect_harold()
    monitor = harold.get_deploy(args.push_id)

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
        monitor.begin(getpass.getuser(), args.command_line,
                      log.log_path, len(args.hosts))

    @deployer.process_host_ended
    @log_exception_and_continue
    def on_process_host_ended(deployer, host):
        index = args.hosts.index(host) + 1
        monitor.progress(host, index)

    @deployer.push_ended
    @log_exception_and_continue
    def on_push_ended(deployer):
        monitor.end()

    @deployer.push_aborted
    @log_exception_and_continue
    def on_push_aborted(deployer, e):
        monitor.abort(str(e))

    @deployer.prompt_error_began
    @log_exception_and_continue
    def on_prompt_error_began(deployer, host, error):
        monitor.error("%s: %s" % (host, error))
