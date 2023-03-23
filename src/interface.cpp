#include <thread>
#include <string>

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
        if ( pos > 0 )
        {
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
        }
    }
    return r;
}


enum avdecc_msg_e
{
  AVDECC_ADP_MSG,
  AVDECC_ACMP_MSG,
  AVDECC_AECP_MSG,
  AVDECC_THREAD_JOIN,
};


union jdksavdecc_du
{
  struct jdksavdecc_adpdu adpdu;
  struct jdksavdecc_acmpdu acmpdu;
  struct jdksavdecc_aecpdu_aem aecpdu_aem;
};


class avdecc_msg_t
{
public:
  avdecc_msg_t(avdecc_msg_e _tp, uint16_t _subtp = 0): 
    tp(_tp), 
    arg_message_type(_subtp)
  {}

  virtual ~avdecc_msg_t() {}

  uint16_t arg_message_type;
  avdecc_msg_e tp;
};


class avdecc_adp_msg_t:
  public avdecc_msg_t
{
public:
  avdecc_adp_msg_t(int msg, uint64_t entity):
    avdecc_msg_t(AVDECC_ADP_MSG, msg),
    arg_entity_id(entity)
  {
  }
  
  int send(struct raw_context *net, struct jdksavdecc_frame *frame, jdksavdecc_adpdu &adpdu) const
  {
    uint16_t message_type_code = arg_message_type;
    int r = 1;

    struct jdksavdecc_eui64 entity_id;
    jdksavdecc_eui64_init_from_uint64( &entity_id, arg_entity_id );

    if ( adp_form_msg( frame, &adpdu, message_type_code, entity_id ) == 0 ) {
      if ( raw_send( net, frame->dest_address.value, frame->payload, frame->length ) > 0 ) {
        // success
        r = 0;
      }
    }
    else {
      // unable to form message
      r = -2;
    }
    
    return r;
  }
  
  uint64_t arg_entity_id;
};


class avdecc_acmp_msg_t:
  public avdecc_msg_t
{
public:
  avdecc_acmp_msg_t(uint64_t _subtp, int argc, const char **argv):
    avdecc_msg_t(AVDECC_ACMP_MSG, _subtp)
  {
    
  }

  int send(struct raw_context *net, struct jdksavdecc_frame *frame, jdksavdecc_acmpdu &acmpdu) const
  {
    return -1;
  }
};

class avdecc_aecp_msg_t:
  public avdecc_msg_t
{
public:
  avdecc_aecp_msg_t(uint64_t _subtp, int argc, const char **argv):
    avdecc_msg_t(AVDECC_AECP_MSG, _subtp)
  {
    
  }

  int send(struct raw_context *net, struct jdksavdecc_frame *frame, jdksavdecc_aecpdu_aem &aecpdu) const
  {
    return -1;
  }
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
            else {
              struct jdksavdecc_frame frame;
              jdksavdecc_frame_init( &frame );
              memcpy( frame.src_address.value, net.m_my_mac, 6 );
              send_msg(&net, &frame, *msg);
            }
            
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
  
  // send_msg is only called from the thread worker
  // can not collide with message reception, i.e., the process method
  int send_msg(struct raw_context *net, struct jdksavdecc_frame *frame, const avdecc_msg_t &msg)
  {
    int r = 1;
    
    if(msg.tp == AVDECC_ADP_MSG) {
      r = static_cast<const avdecc_adp_msg_t &>(msg).send(net, frame, adpdu);
    }
    else if(msg.tp == AVDECC_ACMP_MSG) {
      r = static_cast<const avdecc_acmp_msg_t &>(msg).send(net, frame, acmpdu);
    }
    else if(msg.tp == AVDECC_AECP_MSG) {
      r = static_cast<const avdecc_aecp_msg_t &>(msg).send(net, frame, aecpdu_aem);
    }
    
    return r;
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
  avdecc_t *avdecc = new avdecc_t(intf, adp_cb, acmp_cb, aecp_aem_cb);
  *handle = static_cast<void *>(avdecc); 
  return 0;
}

AVDECC_C_API int AVDECC_C_CALL_CONVENTION AVDECC_destroy(AVDECC_HANDLE handle)
{
  avdecc_t *avdecc = static_cast<avdecc_t *>(handle);
  delete avdecc;
  return 0;
}

AVDECC_C_API int AVDECC_C_CALL_CONVENTION AVDECC_send_adp(AVDECC_HANDLE handle, uint16_t msg, uint64_t entity)
{
  avdecc_t *avdecc = static_cast<avdecc_t *>(handle);
  avdecc_adp_msg_t *m = new avdecc_adp_msg_t(msg, entity);
  avdecc->send.push(m);
  return 0;
}

AVDECC_C_API int AVDECC_C_CALL_CONVENTION AVDECC_get_adpdu(AVDECC_HANDLE handle, struct jdksavdecc_adpdu *adpdu)
{
  avdecc_t *avdecc = static_cast<avdecc_t *>(handle);
  *adpdu = avdecc->adpdu;
  return 0;
}

AVDECC_C_API int AVDECC_C_CALL_CONVENTION AVDECC_set_adpdu(AVDECC_HANDLE handle, const struct jdksavdecc_adpdu *adpdu)
{
  avdecc_t *avdecc = static_cast<avdecc_t *>(handle);
  avdecc->adpdu = *adpdu;
  return 0;
}

AVDECC_C_API int AVDECC_C_CALL_CONVENTION AVDECC_send_acmp(AVDECC_HANDLE handle, uint16_t msg, int argc, char **argv)
{
  avdecc_t *avdecc = static_cast<avdecc_t *>(handle);
  avdecc_acmp_msg_t *m = new avdecc_acmp_msg_t(msg, argc, const_cast<const char **>(argv));
  avdecc->send.push(m);
  return 0;
}

AVDECC_C_API int AVDECC_C_CALL_CONVENTION AVDECC_send_aecp(AVDECC_HANDLE handle, uint16_t msg, int argc, char **argv)
{
  avdecc_t *avdecc = static_cast<avdecc_t *>(handle);
  avdecc_aecp_msg_t *m = new avdecc_aecp_msg_t(msg, argc, const_cast<const char **>(argv));
  avdecc->send.push(m);
  return 0;
}
