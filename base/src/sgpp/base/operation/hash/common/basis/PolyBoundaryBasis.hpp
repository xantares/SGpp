// Copyright (C) 2008-today The SG++ project
// This file is part of the SG++ project. For conditions of distribution and
// use, please see the copyright notice provided with SG++ or at
// sgpp.sparsegrids.org

#pragma once

#include <algorithm>
#include <cmath>
#include <sgpp/base/datatypes/DataVector.hpp>
#include <sgpp/base/exception/factory_exception.hpp>
#include <sgpp/base/operation/hash/common/basis/Basis.hpp>
#include <sgpp/base/operation/hash/common/basis/PolyBasis.hpp>
#include <sgpp/base/tools/GaussLegendreQuadRule1D.hpp>
#include <sgpp/globaldef.hpp>
#include <vector>

namespace sgpp {
namespace base {

/**
 * Polynomial basis functions with boundaries.
 *
 * @version $HEAD$
 */
template <class LT, class IT>
class PolyBoundaryBasis : public Basis<LT, IT> {
 protected:
  /// poly basis
  SPolyBase polyBasis;

 public:
  /**
   * Constructor
   *
   * @param degree the polynom's max. degree
   */
  explicit PolyBoundaryBasis(size_t degree) : polyBasis(degree) {}

  /**
   * Destructor
   */
  ~PolyBoundaryBasis() override {}

  double evalHierToTop(LT level, IT index, DataVector& coeffs, double pos) {
    double result = 0.0;

    if (level > 0) {
      // add left and right boundary point
      result += coeffs[0] * eval(0, 0, pos) + coeffs[1] * eval(0, 1, pos);

      // just evaluate the hierarchical ancestors -> so start with the
      // parent node
      level--;
      index >>= 1;
      index |= 1;
    }

    for (; level >= 1; level--) {
      // the coefficients are shifted by one due to the two boundary points
      // ergo: coeffs = [<left boundary, <right boundary>, 1, 2, ...]
      result += coeffs[level + 1] * eval(level, index, pos);
      index >>= 1;  // == ((index - 1) / 2)
      index |= 1;   // == (index % 2 == 0) ? (index + 1) : index;
    }

    return result;
  }

  size_t getDegree() const override { return polyBasis.getDegree(); }

  double eval(LT level, IT index, double p) override {
    // make sure that the point is inside the unit interval
    if (p < 0.0 || p > 1.0) {
      return 0.0;
    }

    // consider grid points at the boundary
    if (level == 0) {
      if (index == 0) {
        return 1 - p;
      } else {
        // index == 1
        return p;
      }
    }

    // interior basis function
    return polyBasis.eval(level, index, p);
  }

  double eval(LT level, IT index, double p, double offset, double width) {
    // for bounding box evaluation
    // scale p in [offset, offset + width] linearly to [0, 1] and do simple
    // evaluation
    return eval(level, index, (p - offset) / width);
  }

  double evalDx(LT level, IT index, double x) override {
    if ((level == 0) && (index == 0)) {
      return ((0.0 < x && x < 1.0) ? -1.0 : 0.0);
    } else if ((level == 0) && (index == 1)) {
      return ((0.0 < x && x < 1.0) ? 1.0 : 0.0);
    } else {
      // interior basis function
      return polyBasis.evalDx(level, index, x);
    }
  }

  double getIntegral(LT level, IT index) override {
    if (level == 0) {
      return 0.5;
    } else {
      return polyBasis.getIntegral(level, index);
    }
  }
};

// default type-def (unsigned int for level and index)
typedef PolyBoundaryBasis<unsigned int, unsigned int> SPolyBoundaryBase;

}  // namespace base
}  // namespace sgpp
