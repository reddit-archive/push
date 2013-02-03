from kazoo.client import KazooClient
from kazoo.exceptions import KazooException
from kazoo.retry import KazooRetry

from push.hosts import HostSource, HostLookupError


class ZookeeperHostSource(HostSource):
    def __init__(self, config):
        self.zk = KazooClient(config.hosts.zookeeper.connection_string)
        self.zk.start()
        credentials = ":".join((config.hosts.zookeeper.username,
                                config.hosts.zookeeper.password))
        self.zk.add_auth("digest", credentials)
        self.retry = KazooRetry(max_tries=3)

    def get_all_hosts(self):
        try:
            return self.retry(self.zk.get_children, "/server")
        except KazooException as e:
            raise HostLookupError("zk host enumeration failed: %r", e)
