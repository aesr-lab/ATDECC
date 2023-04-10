#pragma once

#include <jdksavdecc.h>

#ifdef __cplusplus
#	define ATDECC_CPP_EXPORT extern "C"
#else // !__cplusplus
#	define ATDECC_CPP_EXPORT
#endif // __cplusplus

#ifdef _WIN32

#	define ATDECC_C_CALL_CONVENTION __stdcall

#	if defined(ATDECC_c_EXPORTS)
#		define ATDECC_C_API ATDECC_CPP_EXPORT __declspec(dllexport)
#	elif defined(ATDECC_c_STATICS)
#		define ATDECC_C_API ATDECC_CPP_EXPORT
#	else // !ATDECC_c_EXPORTS
#		define ATDECC_C_API ATDECC_CPP_EXPORT __declspec(dllimport)
#	endif // ATDECC_c_EXPORTS

#else // !_WIN32

#	define ATDECC_C_CALL_CONVENTION

#	if defined(ATDECC_c_EXPORTS)
#		define ATDECC_C_API ATDECC_CPP_EXPORT __attribute__((visibility("default")))
#	elif defined(ATDECC_c_STATICS)
#		define ATDECC_C_API ATDECC_CPP_EXPORT
#	else // !ATDECC_c_EXPORTS
#		define ATDECC_C_API ATDECC_CPP_EXPORT __attribute__((visibility("default")))
#	endif // ATDECC_c_EXPORTS

#endif // _WIN32


typedef void *ATDECC_HANDLE;
typedef char const* const_string_t;

typedef void (ATDECC_C_CALL_CONVENTION* ATDECC_ADP_CALLBACK)(ATDECC_HANDLE handle, const struct jdksavdecc_frame *frame, const struct jdksavdecc_adpdu *adpdu);
typedef void (ATDECC_C_CALL_CONVENTION* ATDECC_ACMP_CALLBACK)(ATDECC_HANDLE handle, const struct jdksavdecc_frame *frame, const struct jdksavdecc_acmpdu *acmpdu);
typedef void (ATDECC_C_CALL_CONVENTION* ATDECC_AECP_AEM_CALLBACK)(ATDECC_HANDLE handle, const struct jdksavdecc_frame *frame, const struct jdksavdecc_aecpdu_aem *aemdu);

ATDECC_C_API int ATDECC_C_CALL_CONVENTION ATDECC_create(ATDECC_HANDLE *handle, const_string_t intf, ATDECC_ADP_CALLBACK adp_cb, ATDECC_ACMP_CALLBACK acmp_cb, ATDECC_AECP_AEM_CALLBACK aecp_aem_cb);
ATDECC_C_API int ATDECC_C_CALL_CONVENTION ATDECC_destroy(ATDECC_HANDLE handle);

ATDECC_C_API int ATDECC_C_CALL_CONVENTION ATDECC_send(ATDECC_HANDLE handle, const struct jdksavdecc_frame *frame);
