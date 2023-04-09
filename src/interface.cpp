#include <thread>
#include <string>
#include <iostream>
#include <iomanip>

#include <raw.h>
#include <adp.h>
#include <acmp.h>
#include <aecp.h>
#include <avdecc-cmd.h>

#include "interface.h"
#include "queue.hpp"


static struct jdksavdecc_eui64 zero = {0, 0, 0, 0, 0, 0, 0, 0};

static bool _frame_destcheck(struct raw_context *net, const struct jdksavdecc_frame *frame)
{
    return
      frame->ethertype == JDKSAVDECC_AVTP_ETHERTYPE &&
      (
        (memcmp( &frame->dest_address, &jdksavdecc_multicast_adp_acmp, 6 ) == 0) ||
        (memcmp( &frame->dest_address, net->m_my_mac, 6 ) == 0)
      );
}

static int _adp_check_listener(
               const struct jdksavdecc_frame *frame,
               struct jdksavdecc_adpdu *adpdu,
               const struct jdksavdecc_eui64 *target_entity_id )
{
    int r = -1;
    if (frame->payload[0] == JDKSAVDECC_1722A_SUBTYPE_ADP ) {
        bzero( adpdu, sizeof( *adpdu ) );
        if ( jdksavdecc_adpdu_read( adpdu, frame->payload, 0, frame->length ) > 0 ) {
            if ( target_entity_id && jdksavdecc_eui64_compare( &zero, target_entity_id ) != 0 ) {
                if ( jdksavdecc_eui64_compare( &adpdu->header.entity_id, target_entity_id ) == 0 )
                    r = 0;
            }
            else
                r = 0;
        }
    }
    return r;
}

static int _acmp_check_listener(
                         const struct jdksavdecc_frame *frame,
                         struct jdksavdecc_acmpdu *acmpdu,
                         const struct jdksavdecc_eui64 *controller_entity_id,
                         uint16_t sequence_id,
                         const struct jdksavdecc_eui64 *listener_entity_id,
                         uint16_t listener_unique_id )
{
    int r = -1;

    if(frame->payload[0] == JDKSAVDECC_1722A_SUBTYPE_ACMP) {
//        fprintf(stderr, "ACMP\n");
        bzero( acmpdu, sizeof( *acmpdu ) );
        if ( jdksavdecc_acmpdu_read( acmpdu, frame->payload, 0, frame->length ) > 0 ) {
//            fprintf(stderr, "ACMP (type %x)\n", acmpdu->header.message_type);
#if 0
            if ( acmpdu->header.message_type == JDKSAVDECC_ACMP_MESSAGE_TYPE_CONNECT_RX_RESPONSE
                 || acmpdu->header.message_type == JDKSAVDECC_ACMP_MESSAGE_TYPE_DISCONNECT_RX_RESPONSE
                 || acmpdu->header.message_type == JDKSAVDECC_ACMP_MESSAGE_TYPE_GET_RX_STATE_RESPONSE )
            {

                if ( controller_entity_id && jdksavdecc_eui64_compare( &zero, controller_entity_id ) != 0 )
                    if ( jdksavdecc_eui64_compare( &acmpdu->controller_entity_id, controller_entity_id ) == 0 )
                        /* If we care about controller_entity_id then we are caring about sequence_id */
                        r = ( acmpdu->sequence_id == sequence_id )?0:-1;
                    else
                        r = -1;
                else
                    r = 0;

                if ( r == 0 ) {
                    if ( listener_entity_id && jdksavdecc_eui64_compare( &zero, listener_entity_id ) != 0 ) {
                        if ( jdksavdecc_eui64_compare( &acmpdu->listener_entity_id, listener_entity_id ) == 0 )
                            /* If we care about listener_entity_id then we are caring about listener_unique_id */
                            r = ( acmpdu->listener_unique_id == listener_unique_id )?0:-1;
                        else
                            r = -1;
                    }
                    else
                        r = 0;
                }
            }
#else
            r = 0;
#endif
        }
    }
    return r;
}

static int _aecp_aem_check(
                    const struct jdksavdecc_frame *frame,
                    struct jdksavdecc_aecpdu_aem *aem,
                    const struct jdksavdecc_eui64 *controller_entity_id,
                    const struct jdksavdecc_eui64 *target_entity_id,
                    uint16_t sequence_id )
{
    int r = -1;

    if(frame->payload[0] == JDKSAVDECC_1722A_SUBTYPE_AECP) {
        bzero( aem, sizeof( *aem ) );
        ssize_t pos = jdksavdecc_aecpdu_aem_read( aem, frame->payload, 0, frame->length );
        if ( pos > 0 ) {
#if 0
          struct jdksavdecc_aecpdu_common_control_header *h = &aem->aecpdu_header.header;
          if ( h->version == 0 && h->subtype == JDKSAVDECC_SUBTYPE_AECP && h->cd == 1 )
          {
              if (
                  h->message_type == JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_COMMAND ||
                  h->message_type == JDKSAVDECC_AECP_MESSAGE_TYPE_AEM_RESPONSE
                )
              {
                  if ( h->control_data_length >= JDKSAVDECC_AECPDU_AEM_LEN - JDKSAVDECC_COMMON_CONTROL_HEADER_LEN )
                  {
                      if ( !jdksavdecc_eui64_convert_to_uint64(controller_entity_id) || jdksavdecc_eui64_compare( &aem->aecpdu_header.controller_entity_id, controller_entity_id ) == 0 )
                      {
                          if ( !jdksavdecc_eui64_convert_to_uint64(target_entity_id) || jdksavdecc_eui64_compare( &aem->aecpdu_header.header.target_entity_id, target_entity_id ) == 0 )
                          {
                              if ( !sequence_id || aem->aecpdu_header.sequence_id == sequence_id )
                              {
                                  r = 0;
                              }
                          }
                      }
                  }
              }
          }
#else
          r = 0;
#endif
        }
    }
    return r;
}


enum avdecc_msg_e
{
  AVDECC_THREAD_JOIN = 0,
  AVDECC_FRAME,
};


union jdksavdecc_du
{
  struct jdksavdecc_adpdu adpdu;
  struct jdksavdecc_acmpdu acmpdu;
  struct jdksavdecc_aecpdu_aem aecpdu_aem;
  struct jdksavdecc_frame frame;
};


class avdecc_msg_t
{
public:
  avdecc_msg_t(avdecc_msg_e _tp): tp(_tp) {}
  avdecc_msg_e tp;

  virtual int send(struct raw_context *) { return -1; }
};


class avdecc_frame_t:
  public avdecc_msg_t
{
public:
  avdecc_frame_t(const jdksavdecc_frame *f):
    avdecc_msg_t(AVDECC_FRAME)
  {
    memcpy(&frame, f, sizeof(frame));
  }

  virtual int send(struct raw_context *net)
  {
#if 0
    std::cerr << "Send frame, length=" << std::dec << frame.length << ", bytes=[";
    std::cerr << std::hex;
    for(int i = 0; i < frame.length; ) {
      for(int j = 0; j < 4 && i < frame.length; ++i, ++j) 
        std::cerr << std::setfill('0') << std::setw(2) << int(frame.payload[i]);
      std::cerr << ' ';
    }
    std::cerr << std::dec << "]" << std::endl;
#endif
//    jdksavdecc_frame_init( &frame );
    memcpy( frame.src_address.value, net->m_my_mac, 6 );
    if ( raw_send( net, frame.dest_address.value, frame.payload, frame.length ) > 0 )
      return 0;
    else
      return -1;
  }
  
  jdksavdecc_frame frame;
};


class avdecc_join_msg_t:
  public avdecc_msg_t
{
public:
  avdecc_join_msg_t(): avdecc_msg_t(AVDECC_THREAD_JOIN) {}
};


class avdecc_t
{
protected:

  int process(struct raw_context *net, const struct jdksavdecc_frame *frame) const
  {
    // only one struct of the union will be used at a time
    jdksavdecc_du _du;

    if(!_frame_destcheck(net, frame)) return 0;

    // adpdu.header.entity_id was previously set by adp_form_msg in send_msg
    if(_adp_check_listener(frame, &_du.adpdu, &adpdu.header.entity_id ) == 0) {
      adp_cb((AVDECC_HANDLE)this, frame, &_du.adpdu);
      return 1;
    }
    else if (_acmp_check_listener(frame,
                              &_du.acmpdu,
                              &acmpdu.controller_entity_id,
                              acmpdu.sequence_id,
                              &acmpdu.listener_entity_id,
                              acmpdu.listener_unique_id ) == 0 ) {
      acmp_cb((AVDECC_HANDLE)this, frame, &_du.acmpdu);
      return 1;
    }
    else if(_aecp_aem_check(frame,
                         &_du.aecpdu_aem,
                         &aecpdu_aem.aecpdu_header.controller_entity_id,
                         &aecpdu_aem.aecpdu_header.header.target_entity_id,
                         aecpdu_aem.aecpdu_header.sequence_id ) == 0 ) {
      aecp_aem_cb((AVDECC_HANDLE)this, frame, &_du.aecpdu_aem);
      return 1;
    }
    
    return 0;
  }


  static int _process(const void *self, struct raw_context *net, const struct jdksavdecc_frame *frame)
  {
    return static_cast<const avdecc_t *>(self)->process(net, frame);
  }


  static void _worker(avdecc_t *self) { self->worker(); }
    
  void worker()
  {
    struct raw_context net;
    int fd = raw_socket( &net, JDKSAVDECC_AVTP_ETHERTYPE, interface.c_str(), jdksavdecc_multicast_adp_acmp.value);
    if(fd >= 0) {
        bool ending = false;
        while(!ending) {
          // try to send
          avdecc_msg_t *msg = NULL;
          bool have = send.try_pop(msg);
          if(have) {
            if(msg->tp == AVDECC_THREAD_JOIN)
              ending = true;
            else
              msg->send(&net);
            
            delete msg;
          }
          
          // try to receive
          bool recvd = !ending && (avdecc_cmd_process_incoming_raw_once(this, &net, 0, _process) > 0);
          
          if(!have && !recvd)
            // nothing done: yield execution (maybe we could even sleep)
//            std::this_thread::yield();
            std::this_thread::sleep_for(std::chrono::milliseconds(1));
        }

        raw_close( &net );
    }
    else {
      fprintf( stderr, "Unable to open raw socket\n" );
    }
  }
  
public:
  avdecc_t(const char *intf, AVDECC_ADP_CALLBACK _adp_cb, AVDECC_ACMP_CALLBACK _acmp_cb, AVDECC_AECP_AEM_CALLBACK _aecp_aem_cb): 
    interface(intf),
    adp_cb(_adp_cb), 
    acmp_cb(_acmp_cb),
    aecp_aem_cb(_aecp_aem_cb),
    workerthr(NULL)
  {
    bzero(&adpdu, sizeof(adpdu));
    bzero(&acmpdu, sizeof(acmpdu));
    bzero(&aecpdu_aem, sizeof(aecpdu_aem));

    workerthr = new std::thread(_worker, this);
  }
  
  ~avdecc_t()
  {
    // empty queue
    avdecc_msg_t *msg;
    while(send.try_pop(msg)) {}
    
    if(workerthr) {
      // signal thread ending
      send.push(new avdecc_join_msg_t());

      workerthr->join();
      delete workerthr;
    }
  }
  
  std::string interface;
  AVDECC_ADP_CALLBACK adp_cb;
  AVDECC_ACMP_CALLBACK acmp_cb;
  AVDECC_AECP_AEM_CALLBACK aecp_aem_cb;
  std::thread *workerthr;
  SafeQueue<avdecc_msg_t *> send;
  int arg_time_in_ms_to_wait;
  
  struct jdksavdecc_adpdu adpdu;
  struct jdksavdecc_acmpdu acmpdu;
  struct jdksavdecc_aecpdu_aem aecpdu_aem;
};


// C API

AVDECC_C_API int AVDECC_C_CALL_CONVENTION AVDECC_create(AVDECC_HANDLE *handle, const_string_t intf, AVDECC_ADP_CALLBACK adp_cb, AVDECC_ACMP_CALLBACK acmp_cb, AVDECC_AECP_AEM_CALLBACK aecp_aem_cb)
{
  auto avdecc = new avdecc_t(intf, adp_cb, acmp_cb, aecp_aem_cb);
  *handle = static_cast<void *>(avdecc); 
  return 0;
}

AVDECC_C_API int AVDECC_C_CALL_CONVENTION AVDECC_destroy(AVDECC_HANDLE handle)
{
  auto avdecc = static_cast<avdecc_t *>(handle);
  delete avdecc;
  return 0;
}

AVDECC_C_API int AVDECC_C_CALL_CONVENTION AVDECC_send(AVDECC_HANDLE handle, const struct jdksavdecc_frame *frame)
{
  auto avdecc = static_cast<avdecc_t *>(handle);
  auto m = new avdecc_frame_t(frame);
  avdecc->send.push(m);
  return 0;  
}
