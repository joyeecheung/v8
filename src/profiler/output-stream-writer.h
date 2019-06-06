// Copyright 2019 the V8 project authors. All rights reserved.
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

#include "include/v8-profiler.h"
#include "src/utils/memcopy.h"
#include "src/utils/utils.h"
#include "src/utils/vector.h"

namespace v8 {
namespace internal {

template <int bytes>
struct MaxDecimalDigitsIn;
template <>
struct MaxDecimalDigitsIn<4> {
  static const int kSigned = 11;
  static const int kUnsigned = 10;
};
template <>
struct MaxDecimalDigitsIn<8> {
  static const int kSigned = 20;
  static const int kUnsigned = 20;
};

namespace {

template <size_t size>
struct ToUnsigned;

template <>
struct ToUnsigned<4> {
  using Type = uint32_t;
};

template <>
struct ToUnsigned<8> {
  using Type = uint64_t;
};

}  // namespace

template <typename T>
int utoa_impl(T value, const Vector<char>& buffer, int buffer_pos) {
  STATIC_ASSERT(static_cast<T>(-1) > 0);  // Check that T is unsigned
  int number_of_digits = 0;
  T t = value;
  do {
    ++number_of_digits;
  } while (t /= 10);

  buffer_pos += number_of_digits;
  int result = buffer_pos;
  do {
    int last_digit = static_cast<int>(value % 10);
    buffer[--buffer_pos] = '0' + last_digit;
    value /= 10;
  } while (value);
  return result;
}

template <typename T>
int utoa(T value, const Vector<char>& buffer, int buffer_pos) {
  typename ToUnsigned<sizeof(value)>::Type unsigned_value = value;
  STATIC_ASSERT(sizeof(value) == sizeof(unsigned_value));
  return utoa_impl(unsigned_value, buffer, buffer_pos);
}

class OutputStreamWriter {
 public:
  explicit OutputStreamWriter(v8::OutputStream* stream)
      : stream_(stream),
        chunk_size_(stream->GetChunkSize()),
        chunk_(chunk_size_),
        chunk_pos_(0),
        aborted_(false) {
    DCHECK_GT(chunk_size_, 0);
  }
  bool aborted() { return aborted_; }
  void AddCharacter(char c) {
    DCHECK_NE(c, '\0');
    DCHECK(chunk_pos_ < chunk_size_);
    chunk_[chunk_pos_++] = c;
    MaybeWriteChunk();
  }
  void AddString(const char* s) {
    size_t len = strlen(s);
    DCHECK_GE(kMaxInt, len);
    AddSubstring(s, static_cast<int>(len));
  }
  void AddSubstring(const char* s, int n) {
    if (n <= 0) return;
    DCHECK_LE(n, strlen(s));
    const char* s_end = s + n;
    while (s < s_end) {
      int s_chunk_size =
          Min(chunk_size_ - chunk_pos_, static_cast<int>(s_end - s));
      DCHECK_GT(s_chunk_size, 0);
      MemCopy(chunk_.begin() + chunk_pos_, s, s_chunk_size);
      s += s_chunk_size;
      chunk_pos_ += s_chunk_size;
      MaybeWriteChunk();
    }
  }
  void AddNumber(unsigned n) { AddNumberImpl<unsigned>(n, "%u"); }
  void Finalize() {
    if (aborted_) return;
    DCHECK(chunk_pos_ < chunk_size_);
    if (chunk_pos_ != 0) {
      WriteChunk();
    }
    stream_->EndOfStream();
  }

  void AddUChar(unibrow::uchar u) {
    static const char hex_chars[] = "0123456789ABCDEF";
    AddString("\\u");
    AddCharacter(hex_chars[(u >> 12) & 0xF]);
    AddCharacter(hex_chars[(u >> 8) & 0xF]);
    AddCharacter(hex_chars[(u >> 4) & 0xF]);
    AddCharacter(hex_chars[u & 0xF]);
  }

  // Write string wrapped in quotes and escaped.
  void SerializeString(const unsigned char* s) {
    AddCharacter('\n');
    AddCharacter('\"');
    for (; *s != '\0'; ++s) {
      switch (*s) {
        case '\b':
          AddString("\\b");
          continue;
        case '\f':
          AddString("\\f");
          continue;
        case '\n':
          AddString("\\n");
          continue;
        case '\r':
          AddString("\\r");
          continue;
        case '\t':
          AddString("\\t");
          continue;
        case '\"':
        case '\\':
          AddCharacter('\\');
          AddCharacter(*s);
          continue;
        default:
          if (*s > 31 && *s < 128) {
            AddCharacter(*s);
          } else if (*s <= 31) {
            // Special character with no dedicated literal.
            AddUChar(*s);
          } else {
            // Convert UTF-8 into \u UTF-16 literal.
            size_t length = 1, cursor = 0;
            for (; length <= 4 && *(s + length) != '\0'; ++length) {
            }
            unibrow::uchar c =
                unibrow::Utf8::CalculateValue(s, length, &cursor);
            if (c != unibrow::Utf8::kBadChar) {
              AddUChar(c);
              DCHECK_NE(cursor, 0);
              s += cursor - 1;
            } else {
              AddCharacter('?');
            }
          }
      }
    }
    AddCharacter('\"');
  }

 private:
  template <typename T>
  void AddNumberImpl(T n, const char* format) {
    // Buffer for the longest value plus trailing \0
    static const int kMaxNumberSize =
        MaxDecimalDigitsIn<sizeof(T)>::kUnsigned + 1;
    if (chunk_size_ - chunk_pos_ >= kMaxNumberSize) {
      int result =
          SNPrintF(chunk_.SubVector(chunk_pos_, chunk_size_), format, n);
      DCHECK_NE(result, -1);
      chunk_pos_ += result;
      MaybeWriteChunk();
    } else {
      EmbeddedVector<char, kMaxNumberSize> buffer;
      int result = SNPrintF(buffer, format, n);
      USE(result);
      DCHECK_NE(result, -1);
      AddString(buffer.begin());
    }
  }
  void MaybeWriteChunk() {
    DCHECK(chunk_pos_ <= chunk_size_);
    if (chunk_pos_ == chunk_size_) {
      WriteChunk();
    }
  }
  void WriteChunk() {
    if (aborted_) return;
    if (stream_->WriteAsciiChunk(chunk_.begin(), chunk_pos_) ==
        v8::OutputStream::kAbort)
      aborted_ = true;
    chunk_pos_ = 0;
  }

  v8::OutputStream* stream_;
  int chunk_size_;
  ScopedVector<char> chunk_;
  int chunk_pos_;
  bool aborted_;
};

}  // namespace internal
}  // namespace v8
