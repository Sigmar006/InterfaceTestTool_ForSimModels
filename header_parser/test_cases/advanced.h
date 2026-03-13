/**
 * advanced.h — Advanced type test cases for the header parser.
 * Covers: structs, enums, function pointers, default values,
 *         namespaces, C++ references, variadic functions.
 */
#pragma once

#include <stddef.h>

// -------------------------------------------------------------------------
// Types used as parameters
// -------------------------------------------------------------------------

/// A 2-D point.
struct Point {
    float x;
    float y;
};

/// Colour enumeration.
enum Color {
    COLOR_RED   = 0,
    COLOR_GREEN = 1,
    COLOR_BLUE  = 2,
};

// -------------------------------------------------------------------------
// Namespace: geometry
// -------------------------------------------------------------------------

namespace geometry {

/// Computes the Euclidean distance between two points.
double distance(Point p1, Point p2);

/// Scales a point by a scalar factor.
Point scale(Point p, double factor);

/// Applies a user-supplied transform function to a point.
Point transform(Point p, Point (*transform_fn)(Point));

} // namespace geometry

// -------------------------------------------------------------------------
// Namespace: utils
// -------------------------------------------------------------------------

namespace utils {

/**
 * @brief Clamps a value to the range [min, max].
 * @param value  The value to clamp.
 * @param min    Lower bound (default 0).
 * @param max    Upper bound (default 100).
 */
int clamp(int value, int min = 0, int max = 100);

/// Writes a formatted string into buf (like snprintf).
/// Returns the number of characters written.
int format_string(char* buf, size_t buf_size, const char* fmt, ...);

} // namespace utils

// -------------------------------------------------------------------------
// Free functions using the types above
// -------------------------------------------------------------------------

/// Associates a colour with a point (returns a copy).
Point color_point(Point p, Color c);

/// Returns a const reference to the global origin singleton.
const Point& get_origin(void);

/// Swaps two integers via reference parameters.
void swap_ints(int& a, int& b);
