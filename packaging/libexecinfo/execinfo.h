/*
 * backtrace(3) for Haiku on arm64, where HaikuPorts publishes no libexecinfo.
 * Distributed under the terms of the MIT License.
 */
#ifndef _EXECINFO_H_
#define _EXECINFO_H_

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

int backtrace(void** buffer, int size);
char** backtrace_symbols(void* const* buffer, int size);
void backtrace_symbols_fd(void* const* buffer, int size, int fd);

#ifdef __cplusplus
}
#endif

#endif	/* _EXECINFO_H_ */
