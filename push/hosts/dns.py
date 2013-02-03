from __future__ import absolute_import

import dns.name
import dns.zone
import dns.query
import dns.exception
import dns.resolver
import dns.rdtypes

from push.hosts import HostSource, HostLookupError


class DnsHostSource(HostSource):
    def __init__(self, config):
        self.domain = config.hosts.dns.domain

    def get_all_hosts(self):
        """Pull all hosts from DNS by doing a zone transfer."""

        try:
            soa_answer = dns.resolver.query(self.domain, "SOA", tcp=True)
            soa_host = soa_answer[0].mname

            master_answer = dns.resolver.query(soa_host, "A", tcp=True)
            master_addr = master_answer[0].address

            xfr_answer = dns.query.xfr(master_addr, self.domain)
            zone = dns.zone.from_xfr(xfr_answer)
            return [name.to_text()
                    for name, ttl, rdata in zone.iterate_rdatas("A")]
        except dns.exception.DNSException, e:
            raise HostLookupError("host lookup by dns failed: %r" % e)
