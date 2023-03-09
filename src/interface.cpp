#include <thread>
#include <string>

#include <raw.h>
#include <adp.h>
#include <acmp.h>
#include <aecp.h>
#include <avdecc-cmd.h>

#include "interface.h"
#include "queue.hpp"

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
  avdecc_msg_t(avdecc_msg_e _tp, const char *_subtp = NULL): 
    tp(_tp), 
    arg_message_type(_subtp?_subtp:"") 
  {}

  virtual ~avdecc_msg_t() {}

  virtual int send(struct raw_context *net, struct jdksavdecc_frame *frame, jdksavdecc_du &du) const 
  {
    return -1;
  }

  avdecc_msg_e tp;
  std::string arg_message_type;
};

class avdecc_adp_msg_t:
  public avdecc_msg_t
{
public:
  avdecc_adp_msg_t(const char *msg, const char *entity):
    avdecc_msg_t(AVDECC_ADP_MSG, msg),
    arg_entity_id(entity?entity:"")
  {
  }
  
  virtual int send(struct raw_context *net, struct jdksavdecc_frame *frame, jdksavdecc_du &du) const
  {
    struct jdksavdecc_adpdu &adpdu = du.adpdu;
    struct jdksavdecc_eui64 entity_id;
    bzero( &entity_id, sizeof( entity_id ) );
    bzero( &adpdu, sizeof( adpdu ) );
    uint16_t message_type_code;
    int r = 1;

    if ( jdksavdecc_get_uint16_value_for_name( jdksavdecc_adpdu_print_message_type, arg_message_type.c_str(), &message_type_code ) )
    {
      if ( arg_entity_id.length() )
      {
          if ( !jdksavdecc_eui64_init_from_cstr( &entity_id, arg_entity_id.c_str() ) )
          {
              fprintf( stderr, "ADP: invalid entity_id: '%s'\n", arg_entity_id.c_str() );
              r = -1;
          }
      }

      if ( adp_form_msg( frame, &adpdu, message_type_code, entity_id ) == 0 )
      {
          if ( raw_send( net, frame->dest_address.value, frame->payload, frame->length ) > 0 )
          {
            // success
            r = 0;
          }
      }
      else {
        // unable to form message
        r = -2;
      }
    }
    
    return r;
  }
  
  std::string arg_entity_id;
};

class avdecc_acmp_msg_t:
  public avdecc_msg_t
{
public:
  avdecc_acmp_msg_t(int argc, const char **argv):
    avdecc_msg_t(AVDECC_ACMP_MSG, argc?argv[0]:NULL)
  {
    
  }

  virtual int send(struct raw_context *net, struct jdksavdecc_frame *frame, jdksavdecc_du &du) const
  {
    struct jdksavdecc_adpdu &adpdu = du.adpdu;
    return -1;
  }
};

class avdecc_aecp_msg_t:
  public avdecc_msg_t
{
public:
  avdecc_aecp_msg_t(int argc, const char **argv):
    avdecc_msg_t(AVDECC_AECP_MSG, argc?argv[0]:NULL)
  {
    
  }

  virtual int send(struct raw_context *net, struct jdksavdecc_frame *frame, jdksavdecc_du &du) const
  {
    struct jdksavdecc_adpdu &adpdu = du.adpdu;
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

  int process(struct raw_context *, const struct jdksavdecc_frame *frame) const
  {
    // only one will be used
    jdksavdecc_du _du;

    // adpdu.header.entity_id was previously set by adp_form_msg in send_msg
    if(adp_check(frame, &_du.adpdu, &avdecc_du.adpdu.header.entity_id ) == 0) {
      adp_cb(frame, &_du.adpdu);
      return 1;
    }
    else if (acmp_check_listener(frame,
                              &_du.acmpdu,
                              &avdecc_du.acmpdu.controller_entity_id,
                              avdecc_du.acmpdu.sequence_id,
                              &avdecc_du.acmpdu.listener_entity_id,
                              avdecc_du.acmpdu.listener_unique_id ) == 0 ) {
      acmp_cb(frame, &_du.acmpdu);
      return 1;
    }
    else if(aecp_aem_check(frame,
                         &_du.aecpdu_aem,
                         avdecc_du.aecpdu_aem.aecpdu_header.controller_entity_id,
                         avdecc_du.aecpdu_aem.aecpdu_header.header.target_entity_id,
                         avdecc_du.aecpdu_aem.aecpdu_header.sequence_id ) == 0 ) {
      aecp_aem_cb(frame, &_du.aecpdu_aem);
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
            std::this_thread::yield();
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
      r = msg.send(net, frame, avdecc_du);
    }
    else if(msg.tp == AVDECC_ACMP_MSG) {
      // TODO
    }
    else if(msg.tp == AVDECC_AECP_MSG) {
      // TODO
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
  
  jdksavdecc_du avdecc_du;
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

AVDECC_C_API int AVDECC_C_CALL_CONVENTION AVDECC_send_adp(AVDECC_HANDLE handle, const_string_t msg, const_string_t entity)
{
  avdecc_t *avdecc = static_cast<avdecc_t *>(handle);
  avdecc_adp_msg_t *m = new avdecc_adp_msg_t(msg, entity);
  avdecc->send.push(m);
  return 0;
}

AVDECC_C_API int AVDECC_C_CALL_CONVENTION AVDECC_send_acmp(AVDECC_HANDLE handle, int argc, char **argv)
{
  avdecc_t *avdecc = static_cast<avdecc_t *>(handle);
  avdecc_acmp_msg_t *m = new avdecc_acmp_msg_t(argc, const_cast<const char **>(argv));
  avdecc->send.push(m);
  return 0;
}

AVDECC_C_API int AVDECC_C_CALL_CONVENTION AVDECC_send_aecp(AVDECC_HANDLE handle, int argc, char **argv)
{
  avdecc_t *avdecc = static_cast<avdecc_t *>(handle);
  avdecc_aecp_msg_t *m = new avdecc_aecp_msg_t(argc, const_cast<const char **>(argv));
  avdecc->send.push(m);
  return 0;
}
