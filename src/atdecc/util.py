import struct
import netifaces

import .atdecc_api as at


def hexdump(bts):
    return "".join(f"{x:02x}" for x in bts)


def flatten_list(l):
    return [item for sublist in l for item in sublist]

    
api_dicts = {}

def get_api_dict(enum_dict):
    try:
        return api_dicts[enum_dict]
    except KeyError:
        pass
    d = []
    for k in at.__dict__.keys():
        if k.startswith('e_'+enum_dict) and k.endswith("__enumvalues"):
            d.append(k)
    ed = [at.__dict__[di] for di in d]
    api_dicts[enum_dict] = ed
    return ed 


def api_enum(enum_dict, ix):
    dct = get_api_dict(enum_dict)
    for di in dct:
        try:
            return di[ix].replace(enum_dict, '')
        except KeyError:
            pass
    raise KeyError()


def eui_to_str(eui):
    return ":".join(f"{x:02x}" for x in eui.value)


def str_to_avstr(s :str) -> at.struct_jdksavdecc_string:
    """
    Convert Python string s to at.struct_jdksavdecc_string. s can be None
    """
    r = at.struct_jdksavdecc_string()
    r.value[:] = struct.pack("64s", (s or "").encode('ascii'))
    return r

def avstr_to_str(avstr: at.struct_jdksavdecc_string) -> str:
    """
    Convert at.struct_jdksavdecc_string avstr to Python str.
    """
    return bytes(avstr.value).decode('ascii').rstrip('\x00').strip('"')

def pack_struct(s, byte_order='!'): #, level=''):
    """
    Pack structure with given byte-order
    TODO: this should be a class wrapper around a struct
          where the struct.pack format codes and the total length is evaluated with the class.
          The actual packing then happens on a pre-allocated array with the class instance.
    """
    r = bytes()
    for n,t in s._fields_:
        v = getattr(s, n)
        try:
            ln = t._length_
        except AttributeError:
            ln = None
            
        if ln is None:
            try:
                tp = t._type_
            except AttributeError:
                # not an atomic type, assume a struct
                tp = None
            if tp is None:
                vb = pack_struct(v, byte_order=byte_order) #, level=n+'.')
            else:
                assert type(tp) is str
#                print(level+n, t, tp)
                vb = struct.pack(byte_order+tp, v)
        else:
            # is array
            tp = t._type_._type_
#            print(level+n, t, f"{ln}{tp}")
            vb = struct.pack(f"{byte_order}{ln}{tp}", *v)

        r = r+vb
    return r


def uint64_to_eui64(other):
    v = at.struct_jdksavdecc_eui64()
    v.value[:] = (
        ( other >> ( 7 * 8 ) ) & 0xff,
        ( other >> ( 6 * 8 ) ) & 0xff,
        ( other >> ( 5 * 8 ) ) & 0xff,
        ( other >> ( 4 * 8 ) ) & 0xff,
        ( other >> ( 3 * 8 ) ) & 0xff,
        ( other >> ( 2 * 8 ) ) & 0xff,
        ( other >> ( 1 * 8 ) ) & 0xff,
        ( other >> ( 0 * 8 ) ) & 0xff
    )
    return v


def eui64_to_uint64(v):
    return ( v.value[0] << ( 7 * 8 ))+ \
           ( v.value[1] << ( 6 * 8 ))+ \
           ( v.value[2] << ( 5 * 8 ))+ \
           ( v.value[3] << ( 4 * 8 ))+ \
           ( v.value[4] << ( 3 * 8 ))+ \
           ( v.value[5] << ( 2 * 8 ))+ \
           ( v.value[6] << ( 1 * 8 ))+ \
           ( v.value[7] << ( 0 * 8 ))


def uint64_to_eui48(other):
    assert ( other >> ( 6 * 8 ) ) == 0
    v = at.struct_jdksavdecc_eui48()
    v.value[:] = (
        ( other >> ( 5 * 8 ) ) & 0xff,
        ( other >> ( 4 * 8 ) ) & 0xff,
        ( other >> ( 3 * 8 ) ) & 0xff,
        ( other >> ( 2 * 8 ) ) & 0xff,
        ( other >> ( 1 * 8 ) ) & 0xff,
        ( other >> ( 0 * 8 ) ) & 0xff
    )
    return v


def eui48_to_uint64(v):
    return ( v.value[0] << ( 5 * 8 ))+ \
           ( v.value[1] << ( 4 * 8 ))+ \
           ( v.value[2] << ( 3 * 8 ))+ \
           ( v.value[3] << ( 2 * 8 ))+ \
           ( v.value[4] << ( 1 * 8 ))+ \
           ( v.value[5] << ( 0 * 8 ))


def mac_to_eui48(mac):
    # see https://www.geeksforgeeks.org/ipv6-eui-64-extended-unique-identifier/
    if type(mac) is int: #uint64 format
        mac = uint64_to_eui48(mac)
    elif type(mac) is str:
        if ':' in mac:
            mac = mac.split(':')
        elif '-' in mac:
            mac = mac.split('-')
        else:
            raise ValueError('Mac address format unknown')
        # convert hex digits to ints
        mac = [int(m, 16) for m in mac]
    elif type(mac) not in ('list', 'tuple'):
        raise TypeError('Mac address data type unknown')

    v = at.struct_jdksavdecc_eui48()
    v.value[:] = mac
    return v


def mac_to_eid(mac):
    m = mac_to_eui48(mac).value
    v = at.struct_jdksavdecc_eui64()
    v.value[:] = (m[0]^0x02, m[1], m[2], 0xff, 0xf0, m[3], m[4], m[5])
    return v


def intf_to_mac(intf):
    """
    return MAC of network interface (raises exception if not available)
    """
    addrs = netifaces.ifaddresses(intf)
    return addrs[netifaces.AF_LINK][0]['addr']


def intf_to_ip(intf):
    """
    return IP of network interface (raises exception if not available)
    """
    addrs = netifaces.ifaddresses(intf)
    return addrs[netifaces.AF_INET][0]['addr']
