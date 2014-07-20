import push.ssh

auto_events = []


class PushAborted(Exception):
    "Raised when the deploy is cancelled."
    def __init__(self, reason):
        self.reason = reason

    def __str__(self):
        return self.reason


class Event(object):
    """An event that can have an arbitrary number of listeners that get called
    when the event fires."""
    def __init__(self, parent):
        self.parent = parent
        self.listeners = set()

    def register_listener(self, callable):
        self.listeners.add(callable)
        return callable

    def fire(self, *args, **kwargs):
        for listener in self.listeners:
            listener(self.parent, *args, **kwargs)

    __call__ = register_listener


def event_wrapped(fn):
    """Wraps a function "fn" and fires the "fn_began" event before entering
    the function, "fn_ended" after succesfully returning, and "fn_aborted"
    on exception."""
    began_name = fn.__name__ + "_began"
    ended_name = fn.__name__ + "_ended"
    aborted_name = fn.__name__ + "_aborted"
    auto_events.extend((began_name, ended_name, aborted_name))

    def proxy(self, *args, **kwargs):
        getattr(self, began_name).fire(*args, **kwargs)
        try:
            result = fn(self, *args, **kwargs)
        except Exception, e:
            getattr(self, aborted_name).fire(e)
            raise
        else:
            getattr(self, ended_name).fire(*args, **kwargs)
            return result

    return proxy


class Deployer(object):
    def __init__(self, config, args, log, host_source):
        self.config = config
        self.args = args
        self.log = log
        self.host_source = host_source
        self.deployer = push.ssh.SshDeployer(config, args, log)

        for event_name in auto_events:
            setattr(self, event_name, Event(self))

    def _run_fetch_on_host(self, host, origin="origin"):
        for repo in self.args.fetches:
            self.deployer.run_deploy_command(host, "fetch", repo, origin)

    def _deploy_to_host(self, host):
        for repo in self.args.deploys:
            self.deployer.run_deploy_command(host, "deploy", repo,
                                             self.args.revisions[repo])

    @event_wrapped
    def synchronize(self):
        for repo in self.args.fetches:
            self.deployer.run_build_command("synchronize", repo)

        self._run_fetch_on_host(self.config.deploy.build_host)

    @event_wrapped
    def resolve_refs(self):
        for repo in self.args.deploys:
            default_ref = self.config.default_refs.get(repo, "origin/master")
            ref_to_deploy = self.args.revisions.get(repo, default_ref)
            revision = self.deployer.run_build_command("get-revision", repo,
                                                       ref_to_deploy,
                                                       display_output=False)
            self.args.revisions[repo] = revision.strip()

    @event_wrapped
    def build_static(self):
        self.deployer.run_build_command("build-static")

    @event_wrapped
    def deploy_to_build_host(self):
        self._deploy_to_host(self.config.deploy.build_host)

    @event_wrapped
    def process_host(self, host):
        self._run_fetch_on_host(host)
        self._deploy_to_host(host)

        for command in self.args.deploy_commands:
            self.deployer.run_deploy_command(host, *command)

    def needs_static_build(self, repo):
        try:
            self.deployer.run_build_command("needs-static-build", repo,
                                            display_output=False)
        except push.ssh.SshError:
            return False
        else:
            return True

    @event_wrapped
    def push(self):
        try:
            self._push()
        finally:
            self.deployer.shutdown()


    ABORT = "abort"
    RETRY = "retry"
    CONTINUE = "continue"

    def host_error_prompt(self, host, error):
        return self.ABORT

    @event_wrapped
    def prompt_error(self, host, error):
        return self.host_error_prompt(host, error)

    def _push(self):
        if self.args.fetches:
            self.synchronize()

        if self.args.deploys:
            self.resolve_refs()
            self.deploy_to_build_host()

        if self.args.build_static:
            build_static = False
            for repo in self.args.deploys:
                if repo == "public" or self.needs_static_build(repo):
                    build_static = True
                    break

            if build_static:
                self.build_static()
                self.args.deploy_commands.append(["fetch-names"])

        i = 0
        while i < len(self.args.hosts):
            host = self.args.hosts[i]
            i += 1

            # bail out if we're at the end of our journey
            if self.args.stop_before:
                if host == self.args.stop_before:
                    break

            # skip hosts until we get the one to start at
            if self.args.start_at:
                if host == self.args.start_at:
                    self.args.start_at = None
                else:
                    continue

            # skip one host
            if self.args.skip_one:
                self.args.skip_one = False
                continue

            try:
                self.process_host(host)
            except (push.ssh.SshError, IOError) as e:
                if self.host_source.should_host_be_alive(host):
                    response = self.prompt_error(host, e)
                    if response == self.ABORT:
                        raise
                    elif response == self.CONTINUE:
                        continue
                    elif response == self.RETRY:
                        # rewind one host and try again
                        i -= 1
                        continue
                else:
                    self.log.warning("Host %r appears to have been terminated."
                                     " ignoring errors and continuing." % host)

    def cancel_push(self, reason):
        raise PushAborted(reason)
