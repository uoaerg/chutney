#!/usr/bin/env python2

from pyroute2 import IPRoute
from pyroute2 import netns
import netns as enterns
import json

import subprocess

def iplinkshow(ip):
    print([x.get_attr('IFLA_IFNAME') for x in ip.get_links()])

def ipaddrshow(ip):
    for link in ip.get_links():
        print(link.get_attr('IFLA_IFNAME'))
        for addr in ip.get_addr(link['index']):
            print("\t{}".format(addr.get_attr('IFA_ADDRESS')))

def ipnetnsshow():
    print(netns.listnetns())

def create_bridge(ip,bridgename='chtnybridge'):
    if not ip.link_lookup(ifname=bridgename):
        ip.link('add', ifname=bridgename, kind='bridge')
        br = ip.link_lookup(ifname=bridgename)[0]
        ip.link('set', index=br, state='up')

    return bridgename

def add_to_bridge(ip, bridge, interface):
    inf = ip.link_lookup(ifname=interface)[0]
    br = ip.link_lookup(ifname=bridge)[0]
    ip.link('set', index=inf, master=br)

def create_netns(namespace='chtnyns'):
    netns.create(namespace)

    return namespace

# creates an epair and moves the inside part into namespace
# pair is named namespacevX where X is 0 for outside and 1 for inside
def create_epair(ip, namespace):
    outside = namespace + 'v0'
    inside = namespace + 'v1'

    ip.link('add', ifname=outside, kind='veth', peer=inside)

    idx = ip.link_lookup(ifname=inside)[0]
    ip.link('set', index=idx, state='up')
    ip.link('set', index=idx, net_ns_fd=namespace)

    idx = ip.link_lookup(ifname=outside)[0]
    ip.link('set', index=idx, state='up')

    return outside, inside

def set_qdisc(ip, interface, network_profile):
    index = ip.link_lookup(ifname=interface)[0]
    ip.tc('add', 'netem', index, 
        delay=network_profile['delay']*1000,    # convert to micro seconds
        rate=network_profile['bandwidth'],      # TODO unused by pyroute2
        loss=network_profile['drop_rate']       # percentage
    )

def create_chtny_namespace(namespace, bridge, ip4addr, ip6addr, network_profile):
    ip = IPRoute()

    namespace = create_netns('chtny' + namespace)
    outside, inside = create_epair(ip, namespace)

    add_to_bridge(ip, bridge, outside)
    #set_qdisc(ip, outside, network_profile['uplink'])

    with enterns.NetNS(nsname=namespace):
        ip = IPRoute()
        #set_qdisc(ip, inside, network_profile['downlink'])

        idx = ip.link_lookup(ifname="lo")[0]
        ip.link('set', index=idx, state='up')

        idx = ip.link_lookup(ifname=inside)[0]
        ip.link('set', index=idx, state='up')
        ip.addr('add', index=idx, address=ip4addr)
        ip.addr('add', index=idx, address=ip6addr)

        ip.route('add', dst="10.0.0.0/24", oif=idx)

    return namespace

def remove_chtny_namespaces(prefix="chtny"):
    ip = IPRoute()

    for link in ip.get_links():
        name = link.get_attr('IFLA_IFNAME')
        if name.startswith(prefix):
            idx = ip.link_lookup(ifname=name)[0]
            ip.link('del', index=idx)
    
    for ns in netns.listnetns():
        if ns.startswith(prefix):
            netns.remove(ns)


if __name__ == "__main__":
    jsonblob="""
{
        "uplink":{"drop_rate":0, "bandwidth":1000, "delay":200},
        "downlink":{"drop_rate":0, "bandwidth":2000, "delay":200}
}"""

    netprof = json.loads(jsonblob)

    # tidy up before creating anything
    print("tidying up old chtny links and namespaces")
    #remove_chtny_namespaces()

    #bridge = create_bridge(IPRoute())
    #create_chtny_namespace('test', bridge, '10.0.0.2', 'fc00::1', netprof)

    #print("tidying up chtny links and namespaces")
    #remove_chtny_namespaces()

    interface = 'outside'

    index = ip.link_lookup(ifname=interface)[0]
    ip.tc('add', 'netem', index, 
        delay=netprof['delay']*1000,    # convert to micro seconds
        rate=netprof['bandwidth'],      # TODO unused by pyroute2
        loss=netprof['drop_rate']       # percentage
    )
