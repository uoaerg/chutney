import netifaces
import ipaddress

for inf in netifaces.interfaces():
    if netifaces.AF_INET in netifaces.ifaddresses(inf):
        for addr in netifaces.ifaddresses(inf)[netifaces.AF_INET]:
            if 'addr' in addr:
                address = ipaddress.ip_address(addr['addr'])
                if not address.is_loopback and not address.is_link_local:
                    print(address)
                    



    #for addr in netifaces.ifaddresses(inf):
        #if netifaces.AF_INET in addr:
            #for v4 in addr[

#netifaces.ifaddresses('br0')[netifaces.AF_INET][0]['addr']

