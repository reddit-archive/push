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
    def __init__(self, config, args, log):
        self.config = config
        self.args = args
        self.log = log
        self.deployer = push.ssh.SshDeployer(config, args, log)

        for event_name in auto_events:
            setattr(self, event_name, Event(self))

    def _run_fetch_on_host(self, host):
        for repo in self.args.fetches:
            self.deployer.run_deploy_command(host, "fetch", repo)

    def _deploy_to_host(self, host):
        for repo in self.args.deploys:
            self.deployer.run_deploy_command(host, "deploy", repo,
                                             self.args.revisions[repo])

    @event_wrapped
    def synchronize(self):
        self._run_fetch_on_host(self.config.deploy.build_host)

    @event_wrapped
    def resolve_refs(self):
        for repo in self.args.deploys:
            ref_to_deploy = self.args.revisions.get(repo, "origin/master")
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

    def is_plugin(self, repo):
        try:
            self.deployer.run_build_command("is-plugin", repo,
                                            display_output=False)
        except push.ssh.SshError:
            return False
        else:
            return True

    @event_wrapped
    def push(self):
        if self.args.shuffle:
            import random
            random.shuffle(self.args.hosts)

        if self.args.fetches:
            self.synchronize()

        if self.args.deploys:
            self.resolve_refs()

        if self.args.build_static:
            build_static = False
            for repo in self.args.deploys:
                if repo == "public" or self.is_plugin(repo):
                    build_static = True
                    break

            if build_static:
                self.deploy_to_build_host()
                self.build_static()
                self.args.deploy_commands.append(["fetch-names"])

        for host in self.args.hosts:
            # skip hosts until we get the one to start at
            if self.args.start_at:
                if host == self.args.start_at:
                    self.args.start_at = None
                else:
                    continue

            self.process_host(host)

    def cancel_push(self, reason):
        raise PushAborted(reason)
