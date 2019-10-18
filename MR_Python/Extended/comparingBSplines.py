from scalarFunctions import objFuncSGpp as objFuncSGpp
from dataHandling import saveData as saveData
import pysgpp
import numpy as np
import scalarFunctions
import matplotlib.pyplot as plt
from argparse import ArgumentParser
import os
import time
import pickle

import matplotlib
matplotlib.use("TkAgg")

# neon does not have ipdb
try:
    import ipdb
except:
    pass


def plot2DGrid(reSurf):
    grid = reSurf.getGrid()
    gridStorage = grid.getStorage()
    for i in range(gridStorage.getSize()):
        gp = gridStorage.getPoint(i)
        x = gp.getStandardCoordinate(0)
        y = gp.getStandardCoordinate(1)
        plt.plot(x, y, '*')
    plt.plot(0, 0, 'ok')
    plt.plot(0, 1, 'ok')
    plt.plot(1, 0, 'ok')
    plt.plot(1, 1, 'ok')
    plt.show()


def mcMean(objFunc, pdfs, numPoints):
    dim = pdfs.getSize()
    mean = 0
    for i in range(numPoints):
        samplePoint = pdfs.sample()
        mean += objFunc.eval(samplePoint)
    return mean / numPoints


def mcVar(objFunc, pdfs, numPoints):
    dim = pdfs.getSize()
    meanSquare = 0
    for i in range(numPoints):
        samplePoint = pdfs.sample()
        meanSquare += objFunc.eval(samplePoint) ** 2
    meanSquare /= numPoints
    mean = mcMean(objFunc, pdfs, numPoints)
    var = meanSquare - mean ** 2
    return var


def NRMSEFromData(reSurf,
                  objFunc,
                  path):
    # if model evaluations take long, or we want the same Monte Carlo
    # points every time, we can use precalculated Monte carlo points
    # and this outine to measure the error

    # returns vector containing
    # [NRMSE, l2Error, min, max]
    dim = objFunc.getDim()
    funcName = objFunc.getName()
    errorVec = np.zeros(4)

    pointsPath = os.path.join(path, 'precalcEvaluations',
                              funcName, 'evaluationPoints.pkl')
    with open(pointsPath, 'rb') as fp:
        points = pickle.load(fp)
    # vector containing the objective function evaluated at the evaluation
    # points xi_0, xi_1, ...
    # entry[n] is f(xi_n)
    evaluationsPath = os.path.join(
        path, 'precalcEvaluations', funcName, 'evaluations.pkl')
    with open(evaluationsPath, 'rb') as fp:
        trueEvaluations = pickle.load(fp)
    numPoints = len(points)
    print("calculating error with {} precalculated points".format(numPoints))
    point = pysgpp.DataVector(dim)
    l2Error = 0
    for n in range(numPoints):
        for d in range(dim):
            point.set(d, points[n, d])
        approxEval = reSurf.eval(point)
        diff = trueEvaluations[n] - approxEval
        diff = diff**2
        l2Error += diff
    l2Error /= numPoints
    l2Error = np.sqrt(l2Error)

    # get average l2 errors before the normalization
    errorVec[0] = l2Error / (np.max(trueEvaluations) - np.min(trueEvaluations))
    errorVec[1] = l2Error
    errorVec[2] = np.min(trueEvaluations)
    errorVec[3] = np.max(trueEvaluations)

    return errorVec


def interpolateAndError(degree,
                        maxLevel,
                        minPoints,
                        maxPoints,
                        numSteps,
                        numErrPoints,
                        objFunc,
                        gridTypes,
                        refineType,
                        calculateError,
                        dataPath,
                        calculateErrorFromData,
                        calculateMean,
                        calculateVar,
                        quadOrder,
                        initialLevel,
                        numRefine,
                        saveDataFlag,
                        model):
    if refineType == 'regular':
        # ugly wrapper for the regular levels
        sampleRange = range(1, maxLevel + 1)
    else:
        sampleRange = [int(s) for s in np.unique(np.logspace(
            np.log10(minPoints), np.log10(maxPoints), num=numSteps))]

    for i, gridType in enumerate(gridTypes):
        interpolErrors = np.zeros(len(sampleRange))
        nrmsErrors = np.zeros(len(sampleRange))
        means = np.zeros(len(sampleRange))
        meanErrors = np.zeros(len(sampleRange))
        varErrors = np.zeros(len(sampleRange))
        vars = np.zeros(len(sampleRange))
        meanSquares = np.zeros(len(sampleRange))
        gridSizes = np.zeros(len(sampleRange))
        runTimes = np.zeros(len(sampleRange))
        dim = objFunc.getDim()
        lb = objFunc.getLowerBounds()
        ub = objFunc.getUpperBounds()

        if gridType in ['bsplineBoundary', 'nakbsplineboundary']:
            initialLevelwithOffset = initialLevel - 1
        else:
            initialLevelwithOffset = initialLevel
        for j, numPoints in enumerate(sampleRange):
            if refineType == 'mc':
                gridSizes[j] = numPoints
                pdfs = objFunc.getDistributions()
                start = time.time()
                if calculateMean == 1:
                    startMean = time.time()
                    means[j] = mcMean(objFunc, pdfs, numPoints)
                    meanTime = time.time() - startMean
                    realMean = objFunc.getMean()
                    meanErrors[j] = abs(means[j] - realMean)
                    print("mean={:.16E}  real mean={:.16E}  error={:.16E}    (t={})".format(
                        means[j], realMean, meanErrors[j], meanTime))
                if calculateVar == 1:
                    startVar = time.time()
                    vars[j] = mcVar(objFunc, pdfs, numPoints)
                    varTime = time.time() - startVar
                    realVar = objFunc.getVar()
                    varErrors[j] = abs(vars[j] - realVar)
                    print("var={:.16E}  real var={:.16E}  error={:.16E}    (t={})".format(
                        vars[j], realVar, varErrors[j], varTime))
                    print("stdv = {:.16E}".format(np.sqrt(vars[j])))
                runTimes[j] = time.time() - start
            else:
                reSurf = pysgpp.SparseGridResponseSurfaceBspline(objFunc, lb, ub,
                                                                 pysgpp.Grid.stringToGridType(
                                                                     gridType),
                                                                 degree)
                start = time.time()
                verbose = True
                if refineType == 'regular':
                    print("refine for level {}".format(numPoints))
                    level = numPoints  # numPoints is an ugly wrapper for level. Improve this
                    reSurf.regular(numPoints)
                    print("created grid with {} points".format(reSurf.getSize()))
                elif refineType == 'regularByPoints':
                    print("refine regular for {} points".format(numPoints))
                    reSurf.regularByPoints(numPoints, verbose)
                elif refineType == 'surplus':
                    print("refine adaptively for {} points".format(numPoints))
                    reSurf.surplusAdaptive(
                        numPoints, initialLevelwithOffset, numRefine, verbose)
                else:
                    print("this refineType is not supported")

                if calculateError:
                    errorVector = reSurf.nrmsError(objFunc, numErrPoints)
                    interpolErrors[j] = errorVector[1]
                    nrmsErrors[j] = errorVector[0]
                    print("min {}  max {}".format(
                        errorVector[2], errorVector[3]))
                    print("l2 err={}".format(interpolErrors[j]))
                    print("NRMSE ={}".format(nrmsErrors[j]))
                if calculateErrorFromData == 1:
                    errorVector = NRMSEFromData(reSurf, objFunc, dataPath)
                    interpolErrors[j] = errorVector[1]
                    nrmsErrors[j] = errorVector[0]
                    print("min {}  max {}".format(
                        errorVector[2], errorVector[3]))
                    print("l2 err={}".format(interpolErrors[j]))
                    print("NRMSE ={}".format(nrmsErrors[j]))
                if calculateMean == 1:
                    pdfs = objFunc.getDistributions()
                    startMean = time.time()
                    means[j] = reSurf.getMean(pdfs, quadOrder)
                    meanTime = time.time() - startMean
                    realMean = objFunc.getMean()
                    meanErrors[j] = abs(means[j] - realMean)
                    print("mean={:.16E}  real mean={:.16E}  error={:.16E}    (t={})".format(
                        means[j], realMean, meanErrors[j], meanTime))
                if calculateVar == 1:
                    pdfs = objFunc.getDistributions()
                    startVar = time.time()
                    varVec = reSurf.getVariance(pdfs, quadOrder)
                    vars[j] = varVec[0]
                    meanSquares[j] = varVec[1]
                    varTime = time.time() - startVar
                    realVar = objFunc.getVar()
                    varErrors[j] = abs(vars[j] - realVar)
                    print("var={:.16E}  real var={:.16E}  error={:.16E}    (t={})".format(
                        vars[j], realVar, varErrors[j], varTime))
                    print("stdv = {:.16E}".format(np.sqrt(vars[j])))

                    print("points {}    mean {:.16E}      meanSquare {:.16E}      stddv {:.16E}".format(
                        reSurf.getSize(), means[j], meanSquares[j], np.sqrt(vars[j])))

                gridSizes[j] = reSurf.getSize()
                runTimes[j] = time.time() - start

#                 plot2DGrid(reSurf)

            print("\n")
        print('{} {} done (took {}s)\n\n'.format(gridType,
                                                 degree,
                                                 np.sum(runTimes)))
        data = {'gridType': gridType,
                'interpolErrors': interpolErrors,
                'nrmsErrors': nrmsErrors,
                'means': means,
                'meanErrors': meanErrors,
                'vars': vars,
                'varErrors': varErrors,
                'meanSquares': meanSquares,
                'gridSizes': gridSizes,
                'runTimes': runTimes,
                'refineType': refineType,
                'degree': degree,
                'numErrPoints': numErrPoints}

        if saveDataFlag == 1:
            saveData(data, gridType, model, refineType,
                     maxPoints, maxLevel, degree, objFunc)

    return 0


############################ Main ############################
if __name__ == '__main__':
    # parse the input arguments
    parser = ArgumentParser(description='Get a program and run it with input')
    parser.add_argument('--model', default='test', type=str,
                        help='define which test case should be executed')
    parser.add_argument('--dim', default=1, type=int,
                        help='the problems dimensionality')
    parser.add_argument('--scalarModelParameter', default=5, type=int,
                        help='purpose depends on actual model. For monomial its the degree')
    parser.add_argument('--gridType', default= 'nakexmodbound',
                        type=str, help='gridType(s) to use')
    parser.add_argument('--degree', default=135, type=int, help='spline degree')
    parser.add_argument('--refineType', default='surplus',
                        type=str, help='surplus or regular or mc for Monte Carlo')
    parser.add_argument('--maxLevel', default=6, type=int,
                        help='maximum level for regular refinement')
    parser.add_argument('--minPoints', default=1, type=int,
                        help='minimum number of points used')
    parser.add_argument('--maxPoints', default=25000, type=int,
                        help='maximum number of points used')
    parser.add_argument('--numSteps', default=5, type=int,
                        help='number of steps in the [minPoints maxPoints] range')
    parser.add_argument('--initialLevel', default=1, type=int,
                        help='initial regular level for adaptive sparse grids')
    parser.add_argument('--numRefine', default=100, type=int,
                        help='max number of grid points added in refinement steps for sparse grids')
    parser.add_argument('--error', default=1, type=int,
                        help='calculate l2 error')
    parser.add_argument('--numErrPoints', default=100000,
                        type=int, help='number of MC samples for l2 and nrmse')
    parser.add_argument('--errorFromData', default=0, type=int,
                        help='calculate l2 error from precalculated data')
    parser.add_argument('--dataPath', default='/home/rehmemk/git/SGpp/MR_Python/Extended/data', type=str,
                        help='path were results are stored and precalculated data is stored')
    parser.add_argument('--mean', default=0, type=int, help='calculate mean')
    parser.add_argument('--var', default=0, type=int,
                        help='calculate variance')
    parser.add_argument('--quadOrder', default=100, type=int,
                        help='quadrature order for mean and variance calculations')
    parser.add_argument('--saveDataFlag', default=1, type=int, help='saveData')
    parser.add_argument('--numThreads', default=4, type=int,
                        help='number of threads for omp parallelization')

    # configure according to input
    args = parser.parse_args()

    if args.gridType == 'all':
        gridTypes = ['bspline', 'bsplineBoundary', 'modBspline',
                     'bsplineClenshawCurtis',
                     'fundamentalSpline', 'modFundamentalSpline',
                     'nakbspline', 'nakbsplineboundary', 'nakbsplinemodified', 'nakbsplineextended']
    elif args.gridType == 'nak':
        gridTypes = ['nakbspline', 'nakbsplineboundary',
                     'nakbsplinemodified', 'nakbsplineextended']
    elif args.gridType == 'naknobound':
        gridTypes = ['nakbspline', 'nakbsplinemodified', 'nakbsplineextended']
    elif args.gridType == 'nakmodex':
        gridTypes = ['nakbsplinemodified', 'nakbsplineextended']
    elif args.gridType == 'nakexbound':
        gridTypes = ['nakbsplineextended', 'nakbsplineboundary']
    elif args.gridType == 'nakexmodbound':
        gridTypes = ['nakbsplineextended','nakbsplinemodified', 'nakbsplineboundary']
    else:
        gridTypes = [args.gridType]

    if args.degree == 135:
        degrees = [1, 3, 5]
    elif args.degree == 35:
        degrees = [3, 5]
    elif args.degree == 15:
        degrees = [1, 5]
    else:
        degrees = [args.degree]

    if args.refineType == 'mc':
        gridTypes = ['mc']
        degrees = [0]

    pysgpp.omp_set_num_threads(args.numThreads)
    pyFunc = scalarFunctions.getFunction(
        args.model, args.dim, args.scalarModelParameter)
    objFunc = objFuncSGpp(pyFunc)

    # numErrPoints = max(10000, 2 * args.maxPoints)

    pysgpp.Printer.getInstance().setVerbosity(-1)

    for degree in degrees:
        data = interpolateAndError(degree, args.maxLevel, args.minPoints, args.maxPoints, args.numSteps,
                                   args.numErrPoints, objFunc, gridTypes, args.refineType, args.error,
                                   args.dataPath, args.errorFromData, args.mean, args.var,
                                   args.quadOrder, args.initialLevel, args.numRefine, args.saveDataFlag,
                                   args.model)

        # for ANUGA precalculated values
        try:
            pyFunc.cleanUp()
        except:
            pass