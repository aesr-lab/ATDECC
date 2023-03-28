# Initialize Python virtual env

Create virtual Python environment:
`python3 -m venv venv`

Activate Python virtual env:
`source venv/bin/activate`

Install required packages into venv: 
`pip install -r requirements.txt`

Eventual changes in the virtual environment must be stored
`pip freeze > requirements.txt`



# AVB Listener

## ATDECC End Station

An ATDECC End Station is a device that has one or more network ports and has one or more ATDECC Entities.

### An ATDECC End Station shall implement:
— at least one ATDECC Entity
— at least one network interface
— IEEE 1722 control AVTP data unit (AVTPDU) packetization and depacketization

### An ATDECC End Station may implement:
— multiple ATDECC Entities
— one or more network interfaces that implement an appropriate AVB profile as defined in IEEE Std 802.1BA­2011 and corrected by IEEE Std 802.1BATM­2011/Cor 1­2016.
— IEEE 802.1AS time synchronization
— IEEE 1722 stream AVTPDU packetization
— IEEE 1722 stream AVTPDU depacketization
— IEEE 1722 multicast address allocation protocol (MAAP)
— IEEE 802.1Q Clause 34 FQTSS Traffic Shaping
— IEEE 802.1Q Clause 35 Stream Reservation Protocol

### ATDECC Entity
An ATDECC Entity uses one or more of the following ATDECC protocols for discovering or controlling other ATDECC Entities or for being discovered or controlled by other ATDECC Entities:
— ATDECC discovery protocol (ADP)
— ATDECC connection management protocol (ACMP) 
— ATDECC enumeration and control protocol (AECP)

An ATDECC Entity shall:
— Have a single Entity ID that is assigned by the manufacturer or via an ATDECC Proxy Server.
— Implement at least one of the ATDECC Controller, ATDECC Talker, ATDECC Listener, or the ATDECC Responder role.

A discoverable ATDECC Entity is an ATDECC Entity that is capable of advertising itself on a local area network (LAN). An ATDECC Entity that is to be discoverable on a network shall implement:
— 6.2.4 “Advertising Entity State Machine”
— 6.2.5 “Advertising Interface State Machine”
— 6.2.7 “Discovery Interface State Machine”

An ATDECC Entity that is to be discoverable on a network may implement:
— 7.5.1 “Identification Notification”

An ATDECC Entity which has a need to discover other ATDECC Entities on a LAN shall implement: 
— 6.2.6 “Discovery State Machine”

An ATDECC Entity that implements 9.3.5 “ATDECC Entity Model Entity State Machine” that implements 7.4.5 “READ_DESCRIPTOR Command” shall implement:
— 7.2.1 “ENTITY Descriptor”

An ATDECC Entity that implements 9.3.5 “ATDECC Entity Model Entity State Machine” that implements 7.4.5 “READ_DESCRIPTOR Command” may implement:
— 7.2.2 “CONFIGURATION Descriptor”


### ATDECC Listener
An ATDECC Listener is an ATDECC Entity that can sink one or more AVTP Streams.

An ATDECC Listener shall use ATDECC messages transported via IEEE 1722 AVTPDUs. 

An ATDECC Listener shall implement the following:
— IEEE 1722 AVTP Listener
— 8.2.4 “ACMP Listener State Machine”
— 9.3 “ATDECC Entity Model format”
— 9.3.3 “ATDECC Entity Model Commands”
— 9.3.4 “ATDECC Entity Model Responses”
— 9.3.5 “ATDECC Entity Model Entity State Machine”, implementing:
  — 7.4.1 “ACQUIRE_ENTITY Command”
  — 7.4.2 “LOCK_ENTITY Command”
  — 7.4.3 “ENTITY_AVAILABLE Command”
  — 7.4.4 “CONTROLLER_AVAILABLE Command”

An ATDECC Listener may implement the following:
— 9.3.5 “ATDECC Entity Model Entity State Machine”, implementing zero or more of the following:
 xxxx
 
