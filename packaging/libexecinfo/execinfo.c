/*
 * backtrace(3) for Haiku on arm64.
 *
 * The R Chromium binaries published for arm64 were linked against
 * libexecinfo.so.1.1, HaikuPorts' libexecinfo, and HaikuPorts has no arm64
 * repository - so on a clean arm64 system content_shell does not start at
 * all ("Cannot open file libexecinfo.so.1.1"). This provides the same three
 * functions under the same soname.
 *
 * HaikuPorts' version walks frame pointers with __builtin_frame_address, which
 * GCC does not support beyond level 0 on AArch64. The unwinder that libgcc
 * already links walks the .eh_frame instead, which every image here has.
 *
 * Distributed under the terms of the MIT License.
 */
#define _GNU_SOURCE
#include "execinfo.h"

#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <unwind.h>

struct walk {
	void** buffer;
	int size;
	int count;
	int skip;
};

static _Unwind_Reason_Code
collect(struct _Unwind_Context* context, void* cookie)
{
	struct walk* w = (struct walk*)cookie;
	uintptr_t pc = _Unwind_GetIP(context);
	if (pc == 0)
		return _URC_END_OF_STACK;
	if (w->skip > 0) {
		w->skip--;
		return _URC_NO_REASON;
	}
	if (w->count >= w->size)
		return _URC_END_OF_STACK;
	w->buffer[w->count++] = (void*)pc;
	return _URC_NO_REASON;
}

int
backtrace(void** buffer, int size)
{
	if (buffer == NULL || size <= 0)
		return 0;
	/* skip this function's own frame */
	struct walk w = { buffer, size, 0, 1 };
	_Unwind_Backtrace(collect, &w);
	return w.count;
}

/* "image(symbol+0xoff) [0xaddr]", as glibc and libexecinfo print it */
static int
format_frame(char* out, size_t outSize, void* address)
{
	Dl_info info;
	if (dladdr(address, &info) != 0 && info.dli_fname != NULL) {
		const char* image = strrchr(info.dli_fname, '/');
		image = image != NULL ? image + 1 : info.dli_fname;
		if (info.dli_sname != NULL && info.dli_saddr != NULL) {
			return snprintf(out, outSize, "%s(%s+0x%lx) [%p]", image,
				info.dli_sname,
				(unsigned long)((char*)address - (char*)info.dli_saddr),
				address);
		}
		return snprintf(out, outSize, "%s(+0x%lx) [%p]", image,
			(unsigned long)((char*)address - (char*)info.dli_fbase), address);
	}
	return snprintf(out, outSize, "[%p]", address);
}

char**
backtrace_symbols(void* const* buffer, int size)
{
	if (buffer == NULL || size <= 0)
		return NULL;

	/* One allocation, as the interface requires: the caller frees only the
	   returned array. */
	char line[512];
	size_t textSize = 0;
	for (int i = 0; i < size; i++)
		textSize += (size_t)format_frame(line, sizeof(line), buffer[i]) + 1;

	char** result = (char**)malloc(size * sizeof(char*) + textSize);
	if (result == NULL)
		return NULL;
	char* text = (char*)(result + size);
	for (int i = 0; i < size; i++) {
		int length = format_frame(text, textSize, buffer[i]);
		result[i] = text;
		text += length + 1;
		textSize -= length + 1;
	}
	return result;
}

void
backtrace_symbols_fd(void* const* buffer, int size, int fd)
{
	char line[512];
	for (int i = 0; i < size; i++) {
		int length = format_frame(line, sizeof(line) - 1, buffer[i]);
		if (length < 0)
			continue;
		if (length > (int)sizeof(line) - 2)
			length = sizeof(line) - 2;
		line[length] = '\n';
		write(fd, line, length + 1);
	}
}
