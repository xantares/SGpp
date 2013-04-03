/* ****************************************************************************
* Copyright (C) 2010 Technische Universitaet Muenchen                         *
* This file is part of the SG++ project. For conditions of distribution and   *
* use, please see the copyright notice at http://www5.in.tum.de/SGpp          *
**************************************************************************** */
// @author Alexander Heinecke (Alexander.Heinecke@mytum.de)
// @author Roman Karlstetter (karlstetter@mytum.de)

#ifndef OPERATIONMULTIPLEEVALITERATIVE_H
#define OPERATIONMULTIPLEEVALITERATIVE_H

#include "parallel/datadriven/operation/OperationMultipleEvalVectorized.hpp"
#include "base/tools/AlignedMemory.hpp"
#include "parallel/tools/PartitioningTool.hpp"

namespace sg{
namespace parallel{

template<typename KernelImplementation>
class OperationMultipleEvalIterative : public OperationMultipleEvalVectorized
{
public:
	/**
	 * Constructor of OperationMultipleEvalIterativeSPX86Simd
	 *
	 * Within the constructor sg::base::DataMatrixSP Level and sg::base::DataMatrixSP Index are set up.
	 * If the grid changes during your calculations and you don't want to create
	 * a new instance of this class, you have to call rebuildLevelAndIndex before
	 * doing any further mult or multTranspose calls.
	 *
	 * @param storage Pointer to the grid's gridstorage object
	 * @param dataset dataset that should be evaluated
	 */
	OperationMultipleEvalIterative(base::GridStorage *storage, base::DataMatrix *dataset,
								   int gridFrom, int gridTo, int datasetFrom, int datasetTo):
							   OperationMultipleEvalVectorized(storage, dataset)
	{
		m_gridFrom = gridFrom;
		m_gridTo = gridTo;
		m_datasetFrom = datasetFrom;
		m_datasetTo = datasetTo;

		rebuildLevelAndIndex();
	}

	virtual double multVectorized(sg::base::DataVector& alpha, sg::base::DataVector& result)
	{
		// thread creating "benchmark" code
		/*int threadCount = 1;
#ifdef _OPENMP
#pragma omp parallel
		{
			threadCount = omp_get_num_threads();
		}
#endif
		double *openmp_startTime = (double *)aligned_malloc(threadCount*8*sizeof(double), SGPPMEMALIGNMENT); */
		myTimer_->start();

		#pragma omp parallel
		{
			/*
			int myThreadNum = omp_get_thread_num();
			openmp_startTime[myThreadNum*8] = myTimer->stop();
*/
			size_t start;
			size_t end;
			PartitioningTool::getOpenMPPartitionSegment(m_datasetFrom, m_datasetTo, &start, &end, KernelImplementation::getChunkDataPoints());

			KernelImplementation::mult(
						level_,
						index_,
						mask_,
						offset_,
						dataset_,
						alpha,
						result,
						0,
						alpha.getSize(),
						start,
						end);
		}

		// thread creation benchmark code
		/* double max = 0;
		double min = 99999999;
		double avg = 0;
		for (int i = 0; i<threadCount;i++){
			double time_i = openmp_startTime[i*8];
			if(max < time_i){
				max = time_i;
			}
			if (min > time_i) {
				min = time_i;
			}
			avg += time_i;
		}
		avg /= threadCount;
		//std::cout << "Thread creation overhead: " << min << " - " << avg << " - " << max << std::endl;
		//std::cout << "Thread creation overhead: " << max << std::endl;
		aligned_free(openmp_startTime);
*/
		return myTimer_->stop();
	}

	virtual double multTransposeVectorized(sg::base::DataVector& source, sg::base::DataVector& result)
	{
		myTimer_->start();
		result.setAll(0.0);

		#pragma omp parallel
		{
			size_t start;
			size_t end;
			PartitioningTool::getOpenMPPartitionSegment(m_gridFrom, m_gridTo, &start, &end, 1);

			KernelImplementation::multTranspose(
						level_,
						index_,
						mask_,
						offset_,
						dataset_,
						source,
						result,
						start,
						end,
						0,
						dataset_->getNcols());
		}

		return myTimer_->stop();
	}

	virtual void rebuildLevelAndIndex()
	{
		LevelIndexMaskOffsetHelper::rebuild<KernelImplementation::kernelType, OperationMultipleEvalVectorized >(this);
	}

	virtual void updateGridComputeBoundaries(int gridFrom, int gridTo)
	{
		m_gridFrom = gridFrom;
		m_gridTo = gridTo;
	}
};

}
}
#endif // OPERATIONMULTIPLEEVALITERATIVE_H