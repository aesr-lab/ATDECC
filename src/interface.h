#pragma once

#ifdef __cplusplus
#	define AVDECC_CPP_EXPORT extern "C"
#else // !__cplusplus
#	define AVDECC_CPP_EXPORT
#endif // __cplusplus

#ifdef _WIN32

#	define AVDECC_C_CALL_CONVENTION __stdcall

#	if defined(avdecc_c_EXPORTS)
#		define AVDECC_C_API AVDECC_CPP_EXPORT __declspec(dllexport)
#	elif defined(avdecc_c_STATICS)
#		define AVDECC_C_API AVDECC_CPP_EXPORT
#	else // !avdecc_c_EXPORTS
#		define AVDECC_C_API AVDECC_CPP_EXPORT __declspec(dllimport)
#	endif // avdecc_c_EXPORTS

#else // !_WIN32

#	define AVDECC_C_CALL_CONVENTION

#	if defined(avdecc_c_EXPORTS)
#		define AVDECC_C_API AVDECC_CPP_EXPORT __attribute__((visibility("default")))
#	elif defined(avdecc_c_STATICS)
#		define AVDECC_C_API AVDECC_CPP_EXPORT
#	else // !avdecc_c_EXPORTS
#		define AVDECC_C_API AVDECC_CPP_EXPORT __attribute__((visibility("default")))
#	endif // avdecc_c_EXPORTS

#endif // _WIN32


typedef void *AVDECC_HANDLE;

void (AVDECC_C_CALL_CONVENTION* AVDECC_ADP_CALLBACK)(const struct jdksavdecc_frame *frame, const struct jdksavdecc_adpdu *adpdu);
void (AVDECC_C_CALL_CONVENTION* AVDECC_ACMP_CALLBACK)(const struct jdksavdecc_frame *frame, const struct jdksavdecc_acmpdu *acmpdu);
void (AVDECC_C_CALL_CONVENTION* AVDECC_AECP_AEM_CALLBACK)(const struct jdksavdecc_frame *frame, const struct jdksavdecc_aecpdu_aem *aemdu);

AVDECC_C_API error_t AVDECC_C_CALL_CONVENTION AVDECC_create(AVDECC_HANDLE *handle, AVDECC_ADP_CALLBACK adp_cb, AVDECC_ACMP_CALLBACK acmp_cb, AVDECC_AECP_AEM_CALLBACK aecp_aem_cb);

AVDECC_C_API error_t AVDECC_C_CALL_CONVENTION AVDECC_destroy(AVDECC_HANDLE handle);
