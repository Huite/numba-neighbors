import numpy as np
import sklearn.neighbors

sklearn.neighbors.kd_tree
k = 10
dist = np.random.uniform(size=(1, k,), high=100)
idx = np.random.uniform(size=(1, k,), high=1000).astype(np.int64)


sklearn.neighbors.kd_tree.simultaneous_sort(dist, idx)
print(dist[0])
