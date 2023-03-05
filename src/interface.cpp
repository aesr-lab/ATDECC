#include <thread>
#include <string>

#include "interface.h"
#include "queue.hpp"

enum avdecc_msg_e
{
  AVDECC_ADP_MSG,
  AVDECC_ACMP_MSG,
  AVDECC_AECP_MSG,
  AVDECC_JOIN_MSG,
};


class avdecc_msg_t
{
public:
  avdecc_msg_t(avdecc_msg_e _tp): tp(_tp) {}
  virtual ~avdecc_msg_t() {}
};

class avdecc_adp_msg_t:
  public avdecc_msg_t
{
public:
  avdecc_adp_msg_t():
    avdecc_msg_t(AVDECC_ADP_MSG)
  {
    
  }
};

class avdecc_acmp_msg_t:
  public avdecc_msg_t
{
public:
  avdecc_acmp_msg_t():
    avdecc_msg_t(AVDECC_ACMP_MSG)
  {
    
  }
};

class avdecc_aecp_msg_t:
  public avdecc_msg_t
{
public:
  avdecc_aecp_msg_t():
    avdecc_msg_t(AVDECC_AECP_MSG)
  {
    
  }
};

class avdecc_join_msg_t:
  public avdecc_msg_t
{
public:
  avdecc_join_msg_t(): avdecc_msg_t(AVDECC_JOIN_MSG) {}
};



class avdecc_t
{
public:
  avdecc_t(const char *intf, AVDECC_ADP_CALLBACK _adp_cb, AVDECC_ACMP_CALLBACK _acmp_cb, AVDECC_AECP_AEM_CALLBACK _aecp_aem_cb): 
    interface(intf),
    adp_cb(_adp_cb), 
    acmp_cb(_acmp_cb),
    aecp_aem_cb(_aecp_aem_cb),
    worker(NULL)
  {
    worker = new std::thread(this)
  }
  
  ~avdecc_t()
  {
    // empty queue
    avdecc_msg_t *msg;
    while(send.try_pop(msg)) {}
    
    if(worker) {
      // signal thread ending
      send.push(new avdecc_join_msg_t());

      worker->join();
      delete worker;
    }
  }
  
  std::string interface;
  AVDECC_ADP_CALLBACK adp_cb;
  AVDECC_ACMP_CALLBACK acmp_cb;
  AVDECC_AECP_AEM_CALLBACK aecp_aem_cb;
  std::thread *worker;
  SafeQueue<avdecc_msg_t *> send;
  int arg_time_in_ms_to_wait;
  
  struct jdksavdecc_adpdu adpdu;
  struct jdksavdecc_acmpdu acmpdu;
  struct jdksavdecc_aecpdu_aem aemdu_aem;
  
private:
  
  friend static void workerfun(avdecc_t *self)
  {
    struct raw_context net;
    int fd = raw_socket( &net, JDKSAVDECC_AVTP_ETHERTYPE, interface.c_str(), jdksavdecc_multicast_adp_acmp.value);
    if(fd >= 0) {
        bool ending = false;
        while(!ending) {
          // try to send
          avdecc_msg_t *msg = NULL;
          bool have = send.try_pop(msg, 0);
          if(have) {
            if(msg->tp == AVDECC_JOIN_MSG)
              ending = true;
            else {
              struct jdksavdecc_frame frame;
              jdksavdecc_frame_init( &frame );
              memcpy( frame.src_address.value, net.m_my_mac, 6 );
              send_msg(&frame, *msg);
            }
            
            delete msg;
          }
          
          // try to receive
          bool recvd = avdecc_cmd_process_incoming_raw(self, net, 0, process);
          
          if(!have && !recvd)
            // nothing done: yield execution (maybe we could even sleep)
            std::this_thread::yield();
        }

        raw_close( &net );
    }
  }
  
  void send_msg(struct jdksavdecc_frame *frame, const avdecc_msg_t &msg)
  {
    avdecc_msg_e msgtp = msg.tp;
  }

  int process(struct raw_context *, const struct jdksavdecc_frame *frame) 
  {
    struct jdksavdecc_adpdu _adpdu;
    struct jdksavdecc_acmpdu _acmpdu;
    struct jdksavdecc_aecpdu_aem _aecpdu_aem;

    if(adp_check(frame, &_adpdu, &adpdu.header.entity_id ) == 0) {
      adp_cb(frame, &_adpdu);
      return 1;
    }
    else if (acmp_check_listener(frame,
                              &_acmpdu,
                              &acmpdu.controller_entity_id,
                              acmpdu.sequence_id,
                              &acmpdu.listener_entity_id,
                              acmpdu.listener_unique_id ) == 0 ) {
      acmp_cb(frame, &_acmpdu);
      return 1;
    }
    else if(aecp_aem_check(frame,
                         &_aecpdu_aem,
                         aemdu_aem.controller_entity_id,
                         aemdu_aem.header.target_entity_id,
                         aemdu_aem.sequence_id ) == 0 ) {
      aecp_aem_cp(frame, &_aecpdu_aem);
      return 1;
    }
    
    return 0;
  }

  friend AVDECC_CPP_EXPORT static int _process(const void *self, struct raw_context *net, const struct jdksavdecc_frame *frame)
  {
    return static_cast<avdecc_t *>(self)->process(net, frame);
  }

};


// C API

AVDECC_C_API int AVDECC_C_CALL_CONVENTION AVDECC_create(AVDECC_HANDLE *handle, const char *intf, AVDECC_ADP_CALLBACK adp_cb, AVDECC_ACMP_CALLBACK acmp_cb, AVDECC_AECP_AEM_CALLBACK aecp_aem_cb)
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

AVDECC_C_API int AVDECC_C_CALL_CONVENTION AVDECC_send_adp(AVDECC_HANDLE handle, int argc, char **argv)
{
  avdecc_t *avdecc = static_cast<avdecc_t *>(handle);
  avdecc_adp_msg_t *msg = new avdecc_adp_msg_t();
  avdecc->send.push(msg);
  return 0;
}

AVDECC_C_API int AVDECC_C_CALL_CONVENTION AVDECC_send_acmp(AVDECC_HANDLE handle, int argc, char **argv)
{
  avdecc_t *avdecc = static_cast<avdecc_t *>(handle);
  avdecc_acmp_msg_t *msg = new avdecc_acmp_msg_t();
  avdecc->send.push(msg);
  return 0;
}

AVDECC_C_API int AVDECC_C_CALL_CONVENTION AVDECC_send_aecp(AVDECC_HANDLE handle, int argc, char **argv)
{
  avdecc_t *avdecc = static_cast<avdecc_t *>(handle);
  avdecc_aecp_msg_t *msg = new avdecc_aecp_msg_t();
  avdecc->send.push(msg);
  return 0;
}
