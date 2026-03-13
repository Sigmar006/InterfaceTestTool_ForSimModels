#pragma once

#ifdef _WIN32
#  ifdef DEMO_EXPORTS
#    define DEMO_API __declspec(dllexport)
#  else
#    define DEMO_API __declspec(dllimport)
#  endif
#else
#  define DEMO_API __attribute__((visibility("default")))
#endif

/* Simple integer arithmetic */
DEMO_API int add(int a, int b);

/* Mixed-type computation: mode 0=add, 1=multiply, 2=subtract */
DEMO_API double compute(double x, double y, int mode);

/* String processing: copies uppercase of input into output, returns bytes written */
DEMO_API int process_string(const char* input, char* output, int max_len);

/* No-argument status query */
DEMO_API int get_status(void);

/* Boolean predicate */
DEMO_API int is_positive(double value);
