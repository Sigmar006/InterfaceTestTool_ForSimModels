/**
 * simple.h — Basic type test cases for the header parser.
 */
#pragma once

/// Adds two integers and returns the result.
int my_add(int a, int b);

/// Returns the maximum of two floats.
float my_max_float(float x, float y);

/// Computes the square of a double-precision value.
double square(double x);

/// Returns true if the integer is positive.
bool is_positive(int n);

/// Prints a null-terminated string to stdout.
void print_message(const char* msg);

/// Returns a pointer to a static version string.
const char* get_version(void);

/// Allocates a new integer on the heap with the given value.
/// Caller is responsible for freeing the returned pointer.
int* allocate_int(int value);

/// No-op placeholder function.
void do_nothing(void);

/// Multiplies two unsigned values.
unsigned int multiply_uint(unsigned int a, unsigned int b);
