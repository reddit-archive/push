from push.hosts import HostSource


class MockHostSource(HostSource):
    def __init__(self, config):
        self.host_count = config.hosts.mock.host_count

    def get_all_hosts(self):
        return ["app-%02d" % i for i in xrange(self.host_count)]
