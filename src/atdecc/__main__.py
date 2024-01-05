from . import *

from argparse import ArgumentParser
parser = ArgumentParser()
parser.add_argument("-i", "--intf", type=str, default='eth0',
                    help="Network interface (default='%(default)s')")
parser.add_argument("-c", "--config", type=str, default='/etc/atdecc/config.yml',
                    help="Config file (default='%(default)s')")
parser.add_argument("-v", "--valid", type=float, default=62, help="Valid time in seconds (default=%(default)s)")
parser.add_argument("--discover", action='store_true', help="Discover AVDECC entities")
parser.add_argument('-d', "--debug", action='store_true', default=0,
                    help="Enable debug mode")
#    parser.add_argument('-v', "--verbose", action='count', default=0,
#                        help="Increase verbosity")
#    parser.add_argument("args", nargs='*')
args = parser.parse_args()

if args.debug:
    logging.basicConfig(level=logging.DEBUG)
    
entity_info = EntityInfo(
    valid_time=args.valid,
    entity_model_id = 3, # section 6.2.2.8 "If a firmware revision changes the structure of an ATDECC Entity data model then it shall use a new unique entity_model_id."
    entity_capabilities=at.JDKSAVDECC_ADP_ENTITY_CAPABILITY_AEM_SUPPORTED +
                        at.JDKSAVDECC_ADP_ENTITY_CAPABILITY_CLASS_A_SUPPORTED +
                        at.JDKSAVDECC_ADP_ENTITY_CAPABILITY_GPTP_SUPPORTED,
    listener_stream_sinks=2,
    listener_capabilities=at.JDKSAVDECC_ADP_LISTENER_CAPABILITY_IMPLEMENTED +
                          at.JDKSAVDECC_ADP_LISTENER_CAPABILITY_AUDIO_SINK
    # talker_stream_sources=2,
    # talker_capabilities=at.JDKSAVDECC_ADP_TALKER_CAPABILITY_IMPLEMENTED + at.JDKSAVDECC_ADP_TALKER_CAPABILITY_AUDIO_SOURCE
)

with AVDECC(intf=args.intf, entity_info=entity_info, config=args.config, discover=args.discover) as avdecc:

    while(True):
        time.sleep(0.1)
