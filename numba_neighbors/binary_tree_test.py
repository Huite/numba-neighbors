from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from numba_neighbors.binary_tree import simultaneous_sort

import numpy as np
import unittest
from numba_neighbors import binary_tree as bt


class BinaryTreeTest(unittest.TestCase):

    def test_simultaneous_sort(self):
        np.random.seed(123)
        N = 8
        k = 1000
        dist = np.random.uniform(size=(N, k), high=100).astype(np.float32)
        idx = np.random.uniform(size=(N, k), high=1000).astype(np.int64)

        i = np.argsort(dist)
        expected_dist = np.take_along_axis(dist, i, axis=1)
        expected_idx = np.take_along_axis(idx, i, axis=1)

        simultaneous_sort(dist, idx)
        np.testing.assert_allclose(dist, expected_dist)
        np.testing.assert_equal(idx, expected_idx)

    def test_permute_tree(self):
        N = 1024
        data = np.random.uniform(size=(N, 3))

        idx_array = np.arange(N)
        np.random.shuffle(idx_array)

        perm = np.arange(N)
        np.random.shuffle(perm)

        permuted_data, permuted_idx_array = bt.permute_tree(
            data, idx_array, perm)

        actual = permuted_data[permuted_idx_array]
        expected = data[idx_array]
        np.testing.assert_equal(actual, expected)


if __name__ == '__main__':
    unittest.main()
