#cython: wraparound=False, boundscheck=False, cdivision=True, profile=False, nonecheck=False, overflowcheck=False, cdivision_warnings=False, unraisable_tracebacks=False
import cython
from libc.stdlib cimport malloc, free
# import both numpy and the Cython declarations for numpy
import numpy as np
cimport numpy as np

ctypedef int idxtype

cdef extern from 'metis_bridge.c':
	void bridge_partMeshNodal(int* ne, int* nn, idxtype* elmnts, int* etype, int* numflag, int* nparts, int* edgecut, idxtype* epart, idxtype* npart)

def partMeshNodal(int ne, int nn, list elements, int etype, int nparts):

	cdef int i
	cdef int edgecut
	cdef int numflag = 0
	cdef int malloc_elem_c_arr = 0
	cdef np.ndarray elem_arr
	cdef np.ndarray[int, ndim=1, mode="c"] epart_pyarr
	cdef np.ndarray[int, ndim=1, mode="c"] npart_pyarr

	cdef idxtype* elem_c_arr
	cdef idxtype* epart
	cdef idxtype* npart

	elem_arr =  np.ascontiguousarray(np.array(elements, dtype=np.int))

	if elem_arr.dtype == 'int64':
		elem_c_arr = <idxtype* > malloc(elem_arr.shape[0] * sizeof(idxtype))
		malloc_elem_c_arr = 1
		if not(elem_c_arr):
			return None
		for i in xrange(elem_arr.shape[0]):
			elem_c_arr[i] = <idxtype> elem_arr[i]
			if elem_c_arr[i] != elem_arr[i]:
				free(elem_c_arr)
				return None
	else:
		elem_c_arr = <idxtype* > elem_arr.data

	epart = <idxtype* > malloc(ne * sizeof(idxtype))
	if epart == NULL:
		if malloc_elem_c_arr:
			free(elem_c_arr)
		return None

	npart = <idxtype* > malloc(nn * sizeof(idxtype))
	if npart == NULL:
		if malloc_elem_c_arr:
			free(elem_c_arr)
		free(epart)
		return None

	bridge_partMeshNodal(&ne, &nn, elem_c_arr, &etype, &numflag, &nparts, &edgecut, epart, npart)

	epart_pyarr = np.zeros(ne, dtype=np.int32)
	epart_pyarr.data = <char* > epart
	
	npart_pyarr = np.zeros(nn, dtype=np.int32)
	npart_pyarr.data = <char* > npart

	if malloc_elem_c_arr:
		free(elem_c_arr)

	return edgecut, epart_pyarr, npart_pyarr

