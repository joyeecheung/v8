#include <stdio.h>

#if defined(__GNUC__)
#define NOINLINE __attribute__((noinline))
#else
#define NOINLINE
#endif

NOINLINE static int frame_leaf(int value) {
  volatile int preserved = value * 3;
  return preserved;
}

NOINLINE static int frame_middle(int value) {
  return frame_leaf(value + 1);
}

NOINLINE static int frame_root(int value) {
  return frame_middle(value + 1);
}

int main(void) {
  return frame_root(7) == 0;
}