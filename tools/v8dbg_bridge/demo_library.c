#include <inttypes.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>

int describe_frame(uint64_t pc, uint64_t sp, const char* function_name,
                   char* out_buf, size_t out_buf_size) {
  const char* safe_name = function_name != NULL && function_name[0] != '\0'
                              ? function_name
                              : "?";
  int written;

  if (out_buf == NULL || out_buf_size == 0) {
    return 0;
  }

  written = snprintf(out_buf, out_buf_size,
                     "fn=%s pc16=%04" PRIx64 " sp16=%04" PRIx64, safe_name,
                     pc & UINT64_C(0xffff), sp & UINT64_C(0xffff));
  if (written < 0) {
    out_buf[0] = '\0';
    return 0;
  }

  if ((size_t)written >= out_buf_size) {
    out_buf[out_buf_size - 1] = '\0';
  }

  return written;
}
