from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from typing import NamedTuple

import numpy as np
import numba as nb
from numba import prange
from numba import types
from numba_neighbors import binary_tree as bt
import heapq
INT_TYPE = bt.INT_TYPE
FLOAT_TYPE = bt.FLOAT_TYPE
BOOL_TYPE = bt.BOOL_TYPE

INT_TYPE_T = bt.INT_TYPE_T
FLOAT_TYPE_T = bt.FLOAT_TYPE_T
BOOL_TYPE_T = bt.BOOL_TYPE_T

FASTMATH = True

IntArray = np.ndarray
FloatArray = np.ndarray
BoolArray = np.ndarray


class TreeData(NamedTuple):
    n_samples: int
    n_features: int
    leaf_size: int
    n_levels: int
    n_nodes: int
    data: FloatArray
    idx_array: IntArray
    idx_start: IntArray
    idx_end: IntArray
    is_leaf: BoolArray
    node_lower_bounds: FloatArray
    node_upper_bounds: FloatArray


# @nb.njit(inline='always', fastmath=FASTMATH)
# def min_rdist(node_bounds, i_node, x):
#     """Compute the minimum reduced-distance between a point and a node"""
#     rdist = 0.0

#     for j in range(x.size):
#         d_lo = node_bounds[0, i_node, j] - x[j]
#         d_hi = x[j] - node_bounds[1, i_node, j]
#         d = ((d_lo + abs(d_lo)) + (d_hi + abs(d_hi))) / 2
#         rdist += d * d

#     return rdist

# @nb.njit(inline='always', fastmath=FASTMATH)
# def min_dist(node_bounds, i_node, pt):
#     return pow(min_rdist(node_bounds, i_node, pt), 0.5)

# @nb.njit(inline='always', fastmath=FASTMATH)
# def max_rdist(node_bounds, i_node, x):
#     """Compute the maximum reduced-distance between a point and a node"""
#     rdist = 0.0

#     for j in range(x.ize):
#         d_lo = abs(x[j] - node_bounds[0, i_node, j])
#         d_hi = abs(x[j] - node_bounds[1, i_node, j])
#         d = max(d_lo, d_hi)
#         rdist += d * d

#     return rdist

# @nb.njit(inline='always', fastmath=FASTMATH)
# def max_dist(node_bounds, i_node, x):
#     """Compute the maximum distance between a point and a node"""
#     return pow(max_rdist(node_bounds, i_node, x), 0.5)

# @nb.njit(inline='always', fastmath=FASTMATH)
# def _min_max_rdist(node_bounds, i_node, x):
#     """Compute the minimum and maximum distance between a point and a node"""

#     min_dist = 0.0
#     max_dist = 0.0

#     for j in range(x.size):
#         d_lo = node_bounds[0, i_node, j] - x[j]
#         d_hi = x[j] - node_bounds[1, i_node, j]
#         d = (d_lo + abs(d_lo)) + (d_hi + abs(d_hi))
#         min_dist += pow(0.5 * d, 2)
#         max_dist += pow(max(abs(d_lo), abs(d_hi)), 2)
#
# return min_dist, max_dist


@nb.njit(inline='always', fastmath=FASTMATH)
def min_max_rdist(lower_bounds, upper_bounds, x, n_features):
    """Compute the minimum and maximum distance between a point and a node"""

    min_dist = 0.0
    max_dist = 0.0

    for j in range(n_features):
        d_lo = lower_bounds[j] - x[j]
        d_hi = x[j] - upper_bounds[j]
        d = ((d_lo + abs(d_lo)) + (d_hi + abs(d_hi))) * 0.5
        min_dist += d * d
        d = max(abs(d_lo), abs(d_hi))
        max_dist += d * d

    return min_dist, max_dist


@nb.njit(inline='always', fastmath=FASTMATH)
def rdist(x, y):
    # return (x[0] - y[0])**2 + (x[1] - y[1])**2 + (x[2] - y[2])**2
    acc = 0
    for i in range(x.size):
        diff = x[i] - y[i]
        # acc += pow(diff, 2)
        acc += diff * diff
    return acc


# @nb.njit(parallel=True, inline='always')
# def arange(start, stop=None, step=None, dtype=INT_TYPE):
#     diff = start if stop is None else stop - start
#     length = max(int(diff), 0) if step is None else int(diff / step)
#     out = np.empty((length,), dtype=dtype)
#     for i, v in enumerate(nb.prange(start, stop, step)):  # pylint: disable=not-an-iterable
#         out[i] = v
#     return out


@nb.njit(parallel=True, inline='always')
def arange(length, dtype=INT_TYPE):
    out = np.empty((length,), dtype=dtype)
    for i in nb.prange(length):  # pylint: disable=not-an-iterable
        out[i] = i
    return out


@nb.njit(parallel=True)
def get_tree_data(data: FloatArray,
                  leaf_size: int = 40,
                  int_type=INT_TYPE,
                  bool_type=BOOL_TYPE):
    # validate data
    float_type = data.dtype
    if data.size == 0:
        raise ValueError("X is an empty array")

    if leaf_size < 1:
        raise ValueError("leaf_size must be greater than or equal to 1")

    n_samples, n_features = data.shape

    # CHANGE: (n_samples - 1) -> n_samples
    n_levels = 1 + int(np.log2(max(1, n_samples / leaf_size)))
    n_nodes = np.power(2, n_levels) - 1
    # self.idx_array = np.arange(self.n_samples, dtype=int_type)
    idx_array = arange(n_samples, dtype=int_type)

    idx_start = np.zeros((n_nodes,), dtype=int_type)
    idx_end = np.zeros((n_nodes,), dtype=int_type)
    is_leaf = np.zeros((n_nodes,), dtype=bool_type)
    # radius = np.zeros((n_nodes,), dtype=float_type)
    node_lower_bounds = np.full((n_nodes, n_features), np.inf, dtype=float_type)
    node_upper_bounds = np.full((n_nodes, n_features),
                                -np.inf,
                                dtype=float_type)

    tree_data = TreeData(
        n_samples=n_samples,
        n_features=n_features,
        leaf_size=leaf_size,
        n_levels=n_levels,
        n_nodes=n_nodes,
        data=data,
        idx_array=idx_array,
        idx_start=idx_start,
        idx_end=idx_end,
        is_leaf=is_leaf,
        # radius=radius,
        node_lower_bounds=node_lower_bounds,
        node_upper_bounds=node_upper_bounds,
    )
    _recursive_build(0, 0, n_samples, leaf_size, n_nodes, data, idx_array,
                     idx_start, idx_end, is_leaf)
    _update_nodes(
        n_features,
        n_nodes,
        data,
        idx_array,
        idx_start,
        idx_end,
        # radius,
        node_lower_bounds,
        node_upper_bounds,
    )
    return tree_data


@nb.njit()
def _recursive_build(
        i_node: int,
        idx_start_value: int,
        idx_end_value: int,
        leaf_size: int,
        n_nodes: int,
        data: FloatArray,
        idx_array: IntArray,
        idx_start: IntArray,
        idx_end: IntArray,
        is_leaf: BoolArray,
):
    """Recursively build the tree.

    Parameters
    ----------
    tree: TreeData
    i_node : int
        the node for the current step
    idx_start, idx_end : int
        the bounding indices in the idx_array which define the points that
        belong to this node.
    """
    n_points = idx_end_value - idx_start_value
    n_mid = n_points // 2
    idx_array_slice = idx_array[idx_start_value:idx_end_value]
    data = data

    # initialize node data
    # self._init_node(i_node, idx_start, idx_end)
    idx_start[i_node] = idx_start_value
    idx_end[i_node] = idx_end_value

    if 2 * i_node + 1 >= n_nodes:
        is_leaf[i_node] = True
        if n_points > 2 * leaf_size:
            # this shouldn't happen if our memory allocation is correct
            # we'll proactively prevent memory errors, but raise a
            # warning saying we're doing so.
            raise Exception(
                'Internal memory layout is flawed: not enough nodes allocated')
            # import warnings
            # warnings.warn("Internal: memory layout is flawed: "
            #               "not enough nodes allocated")

    elif n_points < 2:
        # again, this shouldn't happen if our memory allocation
        # is correct.  Raise a warning.
        raise Exception(
            'Internal memory layout is flawed: too many nodes allocated')
        # import warnings
        # warnings.warn("Internal: memory layout is flawed: "
        #               "too many nodes allocated")
        # self.is_leaf[i_node] = True

    else:
        # split node and recursively construct child nodes.
        is_leaf[i_node] = False
        i_max = bt.find_node_split_dim(data, idx_array_slice)
        bt.partition_node_indices(data, idx_array_slice, i_max, n_mid)
        idx_mid_value = idx_start_value + n_mid
        _recursive_build(2 * i_node + 1, idx_start_value, idx_mid_value,
                         leaf_size, n_nodes, data, idx_array, idx_start,
                         idx_end, is_leaf)
        _recursive_build(2 * i_node + 2, idx_mid_value, idx_end_value,
                         leaf_size, n_nodes, data, idx_array, idx_start,
                         idx_end, is_leaf)


@nb.njit(parallel=True, fastmath=FASTMATH)
def _update_nodes(
        n_features,
        n_nodes,
        data,
        idx_array,
        idx_start,
        idx_end,
        # radius,
        node_lower_bounds,
        node_upper_bounds,
):
    """Initialize the node for the dataset stored in self.data"""
    for i_node in nb.prange(n_nodes):  # pylint: disable=not-an-iterable
        idx_start_value = idx_start[i_node]
        idx_end_value = idx_end[i_node]

        lower_bounds = node_lower_bounds[i_node]
        upper_bounds = node_upper_bounds[i_node]

        # Compute the actual data range.  At build time, this is slightly
        # slower than using the previously-computed bounds of the parent node,
        # but leads to more compact trees and thus faster queries.

        for i in range(idx_start_value, idx_end_value):
            data_row = data[idx_array[i]]
            for j in range(n_features):
                val = data_row[j]
                lower_bounds[j] = min(lower_bounds[j], val)
                upper_bounds[j] = max(upper_bounds[j], val)


@nb.njit(parallel=True, fastmath=FASTMATH)
def _update_node_radii(n_features, n_nodes, radius, node_lower_bounds,
                       node_upper_bounds):

    for i_node in nb.prange(n_nodes):
        rad = 0
        ub = node_upper_bounds[i_node]
        lb = node_lower_bounds[i_node]
        for j in range(n_features):
            # if upper_bounds[j] != np.inf:
            next_val = 0.5 * abs(ub[j] - lb[j])
            rad += next_val * next_val

        # The radius will hold the size of the circumscribed hypersphere measured
        # with the specified metric: in querying, this is used as a measure of the
        # size of each node when deciding which nodes to split.
        radius[i_node] = pow(rad, 0.5)


@nb.njit()
def rejection_ifp_sample_query_prealloc(
        query_r: float,
        start_nodes: IntArray,
        # -----
        # pre-allocated data
        sample_indices: IntArray,
        dists: FloatArray,
        query_indices: IntArray,
        counts: IntArray,
        consumed: BoolArray,
        min_dists: FloatArray,
        # -----
        # tree data
        n_samples: int,
        n_features: int,
        leaf_size: int,
        n_levels: int,
        n_nodes: int,
        data: FloatArray,
        idx_array: IntArray,
        idx_start: IntArray,
        idx_end: IntArray,
        is_leaf: BoolArray,
        node_lower_bounds: FloatArray,
        node_upper_bounds: FloatArray) -> float:
    # initial rejection sample
    count = rejection_sample_query_prealloc(
        query_r,
        query_r,
        start_nodes,
        sample_indices,
        dists,
        query_indices,
        counts,
        consumed,
        n_samples,
        n_features,
        leaf_size,
        n_levels,
        n_nodes,
        data,
        idx_array,
        idx_start,
        idx_end,
        is_leaf,
        node_lower_bounds,
        node_upper_bounds,
    )

    # update min_dists
    for i in range(count):
        c = counts[i]
        di = dists[i]
        ii = query_indices[i]
        for j in nb.prange(c):  # pylint: disable=not-an-iterable
            dij = di[j]
            iij = ii[j]
            if dij < min_dists[iij]:
                min_dists[iij] = dij

    # construct heap
    min_dists *= -1
    heap = list(zip(min_dists, arange(n_samples)))
    heapq.heapify(heap)
    min_dists *= -1

    # ifp sample
    return ifp_sample_query_prealloc(
        query_r,
        start_nodes,
        sample_indices[count:],
        dists,
        query_indices,
        counts[count:],
        consumed,
        min_dists,
        heap,
        n_samples,
        n_features,
        leaf_size,
        n_levels,
        n_nodes,
        data,
        idx_array,
        idx_start,
        idx_end,
        is_leaf,
        node_lower_bounds,
        node_upper_bounds,
    )


# issues with parallel==True and heapq or zip?
@nb.njit()
def ifp_sample_query_prealloc(
        query_r: float,
        start_nodes: IntArray,
        # -----
        # pre-allocated data
        sample_indices: IntArray,
        dists: FloatArray,
        query_indices: IntArray,
        counts: IntArray,
        consumed: BoolArray,
        min_dists: FloatArray,  # in_size, minimum distances
        heap,  # heap, heap-sorted list of (neg_dist, index) tuples
        # -----
        # tree data
        n_samples: int,
        n_features: int,
        leaf_size: int,
        n_levels: int,
        n_nodes: int,
        data: FloatArray,
        idx_array: IntArray,
        idx_start: IntArray,
        idx_end: IntArray,
        is_leaf: BoolArray,
        node_lower_bounds: FloatArray,
        node_upper_bounds: FloatArray,
        eps: float = 1e-4) -> float:
    count = 0
    sample_size = sample_indices.size
    _, max_neighbors = dists.shape
    top_dist = -np.inf
    while heap:
        top_dist, index = heapq.heappop(heap)
        min_dist = min_dists[index]
        if np.isfinite(min_dist):
            diff = abs(min_dist + top_dist)  # top dist is negative
            if diff > eps:
                continue
        sample_indices[count] = index
        di = dists[count]
        ii = query_indices[count]
        # populate di, ii
        instance_count = counts[count] = _query_radius_single_bottom_up(
            0,
            max_neighbors,
            start_nodes[index],
            data[index],
            di,
            ii,
            query_r,
            n_samples,
            n_features,
            leaf_size,
            n_levels,
            n_nodes,
            data,
            idx_array,
            idx_start,
            idx_end,
            is_leaf,
            node_lower_bounds,
            node_upper_bounds,
        )
        count += 1
        if count >= sample_size:
            break
        for k in range(instance_count):
            dik = di[k]
            iik = ii[k]
            old_dist = min_dists[iik]
            if dik < old_dist:
                min_dists[iik] = dik
                heapq.heappush(heap, (-dik, iik))
    else:
        raise RuntimeError('Should have broken...')
    return -top_dist


@nb.njit(parallel=False)
def rejection_sample_query_prealloc(
        rejection_r: float,
        query_r: float,
        start_nodes: IntArray,
        sample_indices: IntArray,
        dists: FloatArray,
        query_indices: IntArray,
        counts: IntArray,
        consumed: BoolArray,
        n_samples: int,
        n_features: int,
        leaf_size: int,
        n_levels: int,
        n_nodes: int,
        data: FloatArray,
        idx_array: IntArray,
        idx_start: IntArray,
        idx_end: IntArray,
        is_leaf: BoolArray,
        node_lower_bounds: FloatArray,
        node_upper_bounds: FloatArray,
) -> int:
    max_samples, max_count = dists.shape
    if max_samples == 0:
        return 0
    sample_count = 0
    for i in range(n_samples):
        if not consumed[i]:
            sample_indices[sample_count] = i
            counts[sample_count] = _rejection_sample_query_single_bottom_up(
                0,
                max_count,
                start_nodes[i],
                data[i],
                dists[sample_count],
                query_indices[sample_count],
                consumed,
                rejection_r,
                query_r,
                n_samples,
                n_features,
                leaf_size,
                n_levels,
                n_nodes,
                data,
                idx_array,
                idx_start,
                idx_end,
                is_leaf,
                node_lower_bounds,
                node_upper_bounds,
            )
            sample_count += 1
            if sample_count >= max_samples:
                break
    return sample_count


@nb.njit(parallel=True)
def get_node_indices(n_samples: int, n_nodes: int, idx_array: IntArray,
                     idx_start: IntArray, idx_end: IntArray,
                     is_leaf: BoolArray):
    nodes = np.empty((n_samples,), dtype=idx_start.dtype)
    for i in nb.prange(n_nodes):
        if is_leaf[i]:
            nodes[idx_array[idx_start[i]:idx_end[i]]] = i
    return nodes


@nb.njit()
def _rejection_sample_query_single_bottom_up(
        count,
        max_count,
        i_node,
        x,
        dists,
        indices,
        consumed,
        rejection_r,
        query_r,
        n_samples,
        n_features,
        leaf_size,
        n_levels,
        n_nodes,
        data,
        idx_array,
        idx_start,
        idx_end,
        is_leaf,
        lower_bounds,
        upper_bounds,
):
    count = _query_radius_single_bottom_up(
        count,
        max_count,
        i_node,
        x,
        dists,
        indices,
        query_r,
        n_samples,
        n_features,
        leaf_size,
        n_levels,
        n_nodes,
        data,
        idx_array,
        idx_start,
        idx_end,
        is_leaf,
        lower_bounds,
        upper_bounds,
    )
    if rejection_r >= query_r:
        # don't bother doing distance check.
        for i in nb.prange(count):
            consumed[indices[i]] = True
    else:
        for i in nb.prange(count):
            if dists[i] < rejection_r:
                consumed[indices[i]] = True
    return count


@nb.njit(parallel=True)
def query_radius_bottom_up_prealloc(
        X: FloatArray,
        r: float,
        start_nodes: IntArray,
        dists: FloatArray,
        indices: IntArray,
        counts: IntArray,
        n_samples: int,
        n_features: int,
        leaf_size: int,
        n_levels: int,
        n_nodes: int,
        data: FloatArray,
        idx_array: IntArray,
        idx_start: IntArray,
        idx_end: IntArray,
        is_leaf: BoolArray,
        node_lower_bounds: FloatArray,
        node_upper_bounds: FloatArray,
):
    max_counts = min(dists.shape[1], n_samples)
    if max_counts == 0:
        return
    for i in nb.prange(X.shape[0]):  # pylint: disable=not-an-iterable
        counts[i] = _query_radius_single_bottom_up(
            0,
            max_counts,
            start_nodes[i],
            X[i],
            dists[i],
            indices[i],
            r,
            n_samples,
            n_features,
            leaf_size,
            n_levels,
            n_nodes,
            data,
            idx_array,
            idx_start,
            idx_end,
            is_leaf,
            node_lower_bounds,
            node_upper_bounds,
        )


@nb.njit()
def _query_radius_single_bottom_up(
        count,
        max_count,
        i_node,
        x,
        dists,
        indices,
        reduced_r,
        n_samples,
        n_features,
        leaf_size,
        n_levels,
        n_nodes,
        data,
        idx_array,
        idx_start,
        idx_end,
        is_leaf,
        node_lower_bounds,
        node_upper_bounds,
) -> int:
    count = _query_radius_single(
        count,
        max_count,
        i_node,
        x,
        dists,
        indices,
        reduced_r,
        n_samples,
        n_features,
        leaf_size,
        n_levels,
        n_nodes,
        data,
        idx_array,
        idx_start,
        idx_end,
        is_leaf,
        node_lower_bounds,
        node_upper_bounds,
    )
    while count < max_count and i_node != 0:
        parent = (i_node - 1) // 2
        sibling = i_node + 1 if i_node % 2 else i_node - 1
        count = _query_radius_single(
            count,
            max_count,
            sibling,
            x,
            dists,
            indices,
            reduced_r,
            n_samples,
            n_features,
            leaf_size,
            n_levels,
            n_nodes,
            data,
            idx_array,
            idx_start,
            idx_end,
            is_leaf,
            node_lower_bounds,
            node_upper_bounds,
        )
        i_node = parent
    return count


@nb.njit(parallel=True)
def query_radius_prealloc(
        X: FloatArray,
        r: float,
        dists: FloatArray,
        indices: IntArray,
        counts: IntArray,
        n_samples: int,
        n_features: int,
        leaf_size: int,
        n_levels: int,
        n_nodes: int,
        data: FloatArray,
        idx_array: IntArray,
        idx_start: IntArray,
        idx_end: IntArray,
        is_leaf: BoolArray,
        node_lower_bounds: FloatArray,
        node_upper_bounds: FloatArray,
):
    max_results = min(dists.shape[1], n_samples)
    if max_results == 0:
        return
    for i in nb.prange(X.shape[0]):  # pylint: disable=not-an-iterable
        counts[i] = _query_radius_single(
            0,
            max_results,
            0,
            X[i],
            dists[i],
            indices[i],
            r,
            n_samples,
            n_features,
            leaf_size,
            n_levels,
            n_nodes,
            data,
            idx_array,
            idx_start,
            idx_end,
            is_leaf,
            node_lower_bounds,
            node_upper_bounds,
        )


@nb.njit()
def _query_radius_single(
        count,
        max_count,
        i_node,
        x,
        dists,
        indices,
        reduced_r,
        n_samples,
        n_features,
        leaf_size,
        n_levels,
        n_nodes,
        data,
        idx_array,
        idx_start,
        idx_end,
        is_leaf,
        node_lower_bounds,
        node_upper_bounds,
) -> int:
    if count >= max_count:
        return count

    rdist_LB, rdist_UB = min_max_rdist(node_lower_bounds[i_node],
                                       node_upper_bounds[i_node], x, n_features)

    #------------------------------------------------------------
    # Case 1: all node points are outside distance r.
    #         prune this branch.
    if rdist_LB > reduced_r:
        pass

    #------------------------------------------------------------
    # Case 2: all node points are within distance r
    #         add all points to neighbors
    elif rdist_UB <= reduced_r:
        for i in range(idx_start[i_node], idx_end[i_node]):
            index = idx_array[i]
            indices[count] = index
            dists[count] = rdist(x, data[index])
            count += 1
            if count >= max_count:
                break

    #------------------------------------------------------------
    # Case 3: this is a leaf node.  Go through all points to
    #         determine if they fall within radius
    elif is_leaf[i_node]:

        for i in range(idx_start[i_node], idx_end[i_node]):
            rdist_x = rdist(x, data[idx_array[i]])
            if rdist_x <= reduced_r:
                indices[count] = idx_array[i]
                dists[count] = rdist_x
                count += 1
                if count >= max_count:
                    break

    #------------------------------------------------------------
    # Case 4: Node is not a leaf.  Recursively query subnodes
    else:
        count = _query_radius_single(
            count,
            max_count,
            2 * i_node + 1,
            x,
            dists,
            indices,
            reduced_r,
            n_samples,
            n_features,
            leaf_size,
            n_levels,
            n_nodes,
            data,
            idx_array,
            idx_start,
            idx_end,
            is_leaf,
            node_lower_bounds,
            node_upper_bounds,
        )
        count = _query_radius_single(
            count,
            max_count,
            2 * i_node + 2,
            x,
            dists,
            indices,
            reduced_r,
            n_samples,
            n_features,
            leaf_size,
            n_levels,
            n_nodes,
            data,
            idx_array,
            idx_start,
            idx_end,
            is_leaf,
            node_lower_bounds,
            node_upper_bounds,
        )
    return count


##########################################################################


class QueryResult(NamedTuple):
    dists: FloatArray
    indices: IntArray
    counts: IntArray


class RejectionSampleResult(NamedTuple):
    indices: IntArray
    count: int


class IFPSampleResult(NamedTuple):
    indices: IntArray
    min_dists: FloatArray
    min_dist: float


class RejectionSampleQueryResult(NamedTuple):
    sample_result: RejectionSampleResult
    query_result: QueryResult


class IFPSampleQueryResult(NamedTuple):
    sample_result: IFPSampleResult
    query_result: QueryResult


class KDTreeBase(object):

    def _init(self, data: FloatArray, leaf_size: int = 40):
        # assert (data.dtype == self.float_type)
        tree_data = get_tree_data(data,
                                  leaf_size,
                                  int_type=self.int_type,
                                  bool_type=self.bool_type)
        self.n_samples = tree_data.n_samples
        self.n_features = tree_data.n_features
        self.leaf_size = tree_data.leaf_size
        self.n_levels = tree_data.n_levels
        self.n_nodes = tree_data.n_nodes
        self.data = tree_data.data
        self.idx_array = tree_data.idx_array
        self.idx_start = tree_data.idx_start
        self.idx_end = tree_data.idx_end
        self.is_leaf = tree_data.is_leaf
        # self.radius = tree_data.radius
        self.node_lower_bounds = tree_data.node_lower_bounds
        self.node_upper_bounds = tree_data.node_upper_bounds

    @property
    def float_type(self):
        raise NotImplementedError

    @property
    def int_type(self):
        raise NotImplementedError

    @property
    def bool_type(self):
        raise NotImplementedError

    def query_radius_prealloc(self, X: np.ndarray, r: float, dists: np.ndarray,
                              indices: np.ndarray, counts: np.ndarray) -> None:
        return query_radius_prealloc(
            X,
            r,
            dists,
            indices,
            counts,
            n_samples=self.n_samples,
            n_features=self.n_features,
            leaf_size=self.leaf_size,
            n_levels=self.n_levels,
            n_nodes=self.n_nodes,
            data=self.data,
            idx_array=self.idx_array,
            idx_start=self.idx_start,
            idx_end=self.idx_end,
            is_leaf=self.is_leaf,
            node_lower_bounds=self.node_lower_bounds,
            node_upper_bounds=self.node_upper_bounds,
        )

    def query_radius(self, X: np.ndarray, r: float,
                     max_count: int) -> QueryResult:
        n_queries, n_features = X.shape
        assert (n_features == self.n_features)
        shape = (n_queries, max_count)
        dists = np.full(shape, np.inf, dtype=self.float_type)
        indices = np.full(shape, self.n_samples, dtype=self.int_type)
        counts = np.empty((n_queries,), dtype=self.int_type)
        self.query_radius_prealloc(X, r, dists, indices, counts)
        return QueryResult(dists, indices, counts)

    def query_radius_bottom_up_prealloc(self, X: FloatArray, r: float,
                                        start_nodes: IntArray,
                                        dists: FloatArray, indices: IntArray,
                                        counts: IntArray) -> None:
        query_radius_bottom_up_prealloc(
            X,
            r,
            start_nodes,
            dists,
            indices,
            counts,
            n_samples=self.n_samples,
            n_features=self.n_features,
            leaf_size=self.leaf_size,
            n_levels=self.n_levels,
            n_nodes=self.n_nodes,
            data=self.data,
            idx_array=self.idx_array,
            idx_start=self.idx_start,
            idx_end=self.idx_end,
            is_leaf=self.is_leaf,
            node_lower_bounds=self.node_lower_bounds,
            node_upper_bounds=self.node_upper_bounds,
        )

    def query_radius_bottom_up(self, X: FloatArray, r: float,
                               start_nodes: IntArray, max_count: int):
        n = X.shape[0]
        dists = np.full((n, max_count), np.inf, dtype=self.float_type)
        indices = np.zeros((n, max_count), dtype=self.int_type)
        counts = np.zeros((n,), dtype=self.int_type)
        self.query_radius_bottom_up_prealloc(X, r, start_nodes, dists, indices,
                                             counts)
        return QueryResult(dists, indices, counts)

    def rejection_sample_query_prealloc(self, rejection_r: float,
                                        query_r: float, start_nodes: IntArray,
                                        sample_indices: IntArray,
                                        dists: FloatArray,
                                        query_indices: IntArray,
                                        counts: IntArray, consumed: BoolArray):
        return rejection_sample_query_prealloc(
            rejection_r,
            query_r,
            start_nodes,
            sample_indices,
            dists,
            query_indices,
            counts,
            consumed,
            n_samples=self.n_samples,
            n_features=self.n_features,
            leaf_size=self.leaf_size,
            n_levels=self.n_levels,
            n_nodes=self.n_nodes,
            data=self.data,
            idx_array=self.idx_array,
            idx_start=self.idx_start,
            idx_end=self.idx_end,
            is_leaf=self.is_leaf,
            node_lower_bounds=self.node_lower_bounds,
            node_upper_bounds=self.node_upper_bounds,
        )

    def rejection_sample_query(self, rejection_r, query_r,
                               start_nodes: IntArray, max_samples: int,
                               max_counts: int) -> RejectionSampleQueryResult:
        sample_indices = np.full((max_samples,),
                                 self.n_samples,
                                 dtype=self.int_type)
        shape = (max_samples, max_counts)
        dists = np.full(shape, np.inf, dtype=self.float_type)
        query_indices = np.full(shape, self.n_samples, dtype=self.int_type)
        counts = np.full((max_samples,), -1, dtype=self.int_type)
        consumed = np.zeros((self.n_samples,), dtype=self.bool_type)
        sample_count = self.rejection_sample_query_prealloc(
            rejection_r, query_r, start_nodes, sample_indices, dists,
            query_indices, counts, consumed)

        return RejectionSampleQueryResult(
            RejectionSampleResult(sample_indices, sample_count),
            QueryResult(dists, query_indices, counts))

    def ifp_sample_query_prealloc(
            self,
            query_r: float,
            start_nodes: IntArray,
            # -----
            # pre-allocated data
            sample_indices: IntArray,
            dists: FloatArray,
            query_indices: IntArray,
            counts: IntArray,
            consumed: BoolArray,
            min_dists: FloatArray,  # in_size, minimum distances
            heap,  # heap, heap-sorted list of (neg_dist, index) tuples
    ) -> float:
        return ifp_sample_query_prealloc(
            query_r,
            start_nodes,
            sample_indices,
            dists,
            query_indices,
            counts,
            consumed,
            min_dists,
            heap,
            self.n_samples,
            self.n_features,
            self.leaf_size,
            self.n_levels,
            self.n_nodes,
            self.data,
            self.idx_array,
            self.idx_start,
            self.idx_end,
            self.is_leaf,
            self.node_lower_bounds,
            self.node_upper_bounds,
        )

    def ifp_sample_query(self, query_r: float, start_nodes: IntArray,
                         sample_size: int,
                         max_counts: int) -> IFPSampleQueryResult:
        sample_indices = np.full((sample_size,),
                                 self.n_samples,
                                 dtype=self.int_type)
        shape = (sample_size, max_counts)
        dists = np.full(shape, np.inf, dtype=self.float_type)
        query_indices = np.full(shape, self.n_samples, dtype=self.int_type)
        counts = np.full((sample_size,), -1, dtype=self.int_type)
        consumed = np.zeros((self.n_samples,), dtype=self.bool_type)
        min_dists = np.full((self.n_samples,), -np.inf, dtype=self.float_type)

        heap = list(zip(min_dists, arange(self.n_samples,)))
        min_dists *= -1
        min_dist = self.ifp_sample_query_prealloc(query_r, start_nodes,
                                                  sample_indices, dists,
                                                  query_indices, counts,
                                                  consumed, min_dists, heap)

        return IFPSampleQueryResult(
            IFPSampleResult(sample_indices, min_dists, min_dist),
            QueryResult(dists, query_indices, counts))

    def rejection_ifp_sample_query_prealloc(
            self,
            query_r: float,
            start_nodes: IntArray,
            # -----
            # pre-allocated data
            sample_indices: IntArray,
            dists: FloatArray,
            query_indices: IntArray,
            counts: IntArray,
            consumed: BoolArray,
            min_dists: FloatArray) -> float:
        return rejection_ifp_sample_query_prealloc(
            query_r,
            start_nodes,
            sample_indices,
            dists,
            query_indices,
            counts,
            consumed,
            min_dists,
            self.n_samples,
            self.n_features,
            self.leaf_size,
            self.n_levels,
            self.n_nodes,
            self.data,
            self.idx_array,
            self.idx_start,
            self.idx_end,
            self.is_leaf,
            self.node_lower_bounds,
            self.node_upper_bounds,
        )

    def rejection_ifp_sample_query(self, query_r: float, start_nodes: IntArray,
                                   sample_size: int,
                                   max_counts: int) -> IFPSampleQueryResult:
        sample_indices = np.full((sample_size,),
                                 self.n_samples,
                                 dtype=self.int_type)
        shape = (sample_size, max_counts)
        dists = np.full(shape, np.inf, dtype=self.float_type)
        query_indices = np.full(shape, self.n_samples, dtype=self.int_type)
        counts = np.full((sample_size,), -1, dtype=self.int_type)
        consumed = np.zeros((self.n_samples,), dtype=self.bool_type)
        min_dists = np.full((self.n_samples,), np.inf, dtype=self.float_type)

        min_dist = self.rejection_ifp_sample_query_prealloc(
            query_r, start_nodes, sample_indices, dists, query_indices, counts,
            consumed, min_dists)

        return IFPSampleQueryResult(
            IFPSampleResult(sample_indices, min_dists, min_dist),
            QueryResult(dists, query_indices, counts))

    def get_node_indices(self):
        return get_node_indices(n_samples=self.n_samples,
                                n_nodes=self.n_nodes,
                                idx_array=self.idx_array,
                                idx_start=self.idx_start,
                                idx_end=self.idx_end,
                                is_leaf=self.is_leaf)


@nb.jitclass([
    ('n_samples', INT_TYPE_T),
    ('n_features', INT_TYPE_T),
    ('leaf_size', INT_TYPE_T),
    ('n_levels', INT_TYPE_T),
    ('n_nodes', INT_TYPE_T),
    ('data', FLOAT_TYPE_T[:, ::1]),
    ('idx_array', INT_TYPE_T[::1]),
    ('idx_start', INT_TYPE_T[::1]),
    ('idx_end', INT_TYPE_T[::1]),
    ('is_leaf', BOOL_TYPE_T[::1]),
    # ('radius', FLOAT_TYPE_T[:]),
    ('node_lower_bounds', FLOAT_TYPE_T[:, ::1]),
    ('node_upper_bounds', FLOAT_TYPE_T[:, ::1]),
])
class KDTree(KDTreeBase):

    def __init__(self, data: FloatArray, leaf_size: int = 40):
        self._init(data=data, leaf_size=leaf_size)

    @property
    def float_type(self):
        return FLOAT_TYPE

    @property
    def int_type(self):
        return INT_TYPE

    @property
    def bool_type(self):
        return BOOL_TYPE
