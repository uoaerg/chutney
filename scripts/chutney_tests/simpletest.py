import time
import multiprocessing
from multiprocessing import Process
import socket
import sys
import struct
import ipaddress
from nsenter import Namespace

import hexdump
#from testpyroute import *

# run a loop back test for each client in the network
def run_test(network):
    boot_time= network._dfltEnv['bootstrap_time']

    testsrun = 0
    # walk the network, find the first client network to use
    for node in network._nodes:
        if node._env['nick'].endswith('c'):
            if verify_network(node, boot_time=boot_time):
                testsrun = testsrun + 1

    if testsrun == 0:
        print('run_test: unable to find a client node for test')
        return False

def verify_network(client, boot_time=60):

    laddr = client._env['ipv4_addr']
    socksport = client._env['socksport']
    print("control port {}".format(client._env['controlport']))

    namespace = '/var/run/netns/chtny' + client._env['nick']

    wait_time = boot_time
    start_time = time.time()
    end_time = start_time + wait_time
    print("Verifying data transmission: (retrying for up to %d seconds)"
          % wait_time)
    status = False
    # Keep on retrying the verify until it succeeds or times out
    while not status and time.time() < end_time:
        # TrafficTester connections time out after ~3 seconds
        # a TrafficTester times out after ~10 seconds if no data is being sent
        status = loop_traffic(socksport, laddr, 4747, namespace)
        # Avoid madly spewing output if we fail immediately each time
        if not status:
            time.sleep(5)
    print("Transmission: %s" % ("Success" if status else "Failure"))
    if not status:
        print("Set CHUTNEY_DEBUG to diagnose.")
    return status

def loop_traffic(socksport, listenaddress, listenport, namespace):
    recv_end, send_end = multiprocessing.Pipe(False)

    clientps = Process(target=echo_client, args=(send_end, namespace, 
        socksport, listenaddress, listenport))
    serverps = Process(target=echo_server, args=(namespace, 
        listenaddress, listenport))

    serverps.start()
    clientps.start()

    #serverps.join()
    clientps.join()

    result = recv_end.recv()
    if not result:
        print("client returned error")

    if serverps.is_alive():
        serverps.terminate()

    return result
    
def echo_client(pipe, namespace, socksport, address, port):

    with Namespace(namespace, 'net'):
        sendsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sendsock.settimeout(1)

        if not connect_via_socks5(sendsock, socksport, address, port):
            print("connect_via_socks5 failed")
            pipe.send(False)
            return
        senddata = "hello  world tst"

        for x in range(10):
            sendsock.send(senddata)

            try:
                recvdata = sendsock.recv(1024)
            except socket.timeout:
                print("simpletest: timeout waiting for echo server")
                sendsock.shutdown(2)
                sendsock.close()
                pipe.send(False)
                return

            if recvdata != senddata:
                print("ERROR recv'd data is not equal sent data")

        sendsock.shutdown(2)
        sendsock.close()

        pipe.send(True)
        return 

def echo_server(namespace, listenaddress, listenport):
    with Namespace(namespace, 'net'):
        #listensock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        listensock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        listensock.bind((listenaddress, listenport))
        listensock.listen(1)

        conn, addr = listensock.accept()

        while True:
            data = conn.recv(1024)
            if (len(data)) == 0:
                break
            conn.send(data)
        listensock.close()

def connect_via_socks5(s, socksport, addr, port):
    socksaddr = "127.0.0.1"

    print("connecting to {}:{} via {}:{}".format(addr,str(port), socksaddr, str(socksport)))
    s.connect(("127.0.0.1", socksport))

    s.send(socks5_auth_cmd(addr, port))
    data = s.recv(2)

    if not socks5_parse_auth(data):
        print('bad auth response')
        return False

    s.send(socks5_connect_cmd(addr, port))

    #response field len: version status pad addrtype 
    try: 
        data = s.recv(10)
    except socket.timeout:
        print("timeout waiting for socks connect cmd")
        return False

    addr_type = socks5_parse_connect(data)

    if addr_type == None:
        print('bad connect response')
        return False

#    if addr_type == 0x04:
#        server_addr, server_port = struct.unpack("!16sH", data[4:])
#        server_addr = ipaddress.ip_address(server_addr)
#        print("socks5 connect succeeded with ipv6, connected on [{}]:{}".format(server_addr,port))
#    elif addr_type == 0x01:
#        server_addr, server_port = struct.unpack("!4sH", data[4:])
#        server_addr = ipaddress.ip_address(server_addr)
#        print("socks5 connect succeeded with ipv4, connected on {}:{}".format(server_addr,port))
#    else:
#        print("invalid address type {}".format(addr_type))
#        return False

    return True

def socks5_auth_cmd(addr, port):
    return '\x05\x01\x00'

def socks5_connect_cmd(addr, port):
    return '\x05\x01\x00\x01'  + ipaddress.ip_address(addr).packed + struct.pack("!H", port)

def socks5_parse_auth(data):
    version, result = struct.unpack("!bb", data)

    if version == 0x05 and result == 0x00:
        return True
    else:
        return False

def socks5_parse_connect(data):
    version, status, addr_type = struct.unpack("!bbxb", data[:4])

    if version != 0x05 and status != 0x00:
        print("socks5 connect failed")
        print("len {} version {} status {} addrtype {}".format(len(data), version, status, addr_type))
        return None
    else:
        return addr_type

if __name__ == "__main__":
    #print(loop_traffic(9050, "2001:630:42:110:1c7e:6cff:fecf:f737", 4747, "/var/run/netns/ns1"))
    print(loop_traffic(1080, "10.0.0.4", 4747, "/var/run/netns/ns1"))
