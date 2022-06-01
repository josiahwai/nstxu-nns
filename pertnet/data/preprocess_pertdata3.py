from sklearn.decomposition import PCA
import numpy as np
import matplotlib.pyplot as plt
import scipy.io as sio
import os
from mds_utils import *
import copy
import os
from pdb import set_trace
import mat73
from scipy.ndimage import median_filter
from sklearn.preprocessing import normalize
from easydict import EasyDict

def main():
    
    # Settings
    ROOT = os.environ['NN_ROOT']
    smoothit = False  # smoothit=True is not recommended
    oversample = False 
    smooth_coeffs = False # smooth_coeffs=True is not recommended
    window = None     # window size if smoothit = True
    evt = 0.99        # explained variance threshold
    t_rampup = 0.1  
    t_rampdown = 0.1
    ncomps_max = 20
    save_suffix = '013.dat'
    save_dir = ROOT + 'pertnet/data/datasets/'

    # load data
    datadir = ROOT + 'data/rawdata/data_by_var/'
    traindir = datadir + 'train/'
    valdir = datadir + 'val/'
    testdir = datadir + 'test/'
   
    xnames = ['xmat', 'gamma', 'pprime', 'ffprim', 'pres','rmaxis','zmaxis',
              'psirz', 'coil_currents', 'vessel_currents', 'pcurrt', 'rcur', 'zcur', 'ip',
              'qpsi', 'psimag', 'psibry', 'rbbbs', 'zbbbs', 'psizr_pla', 'wmhd', 'li', 
              'psizr_pla_iv', 'betap']

    # xnames += ['dpsidix_smooth_coil1']
    xnames += ['dpsidix_smooth_coil' + str(icoil) for icoil in range(1,55)]
    
    xnames += ['dpsidbetap', 'dpsidli']

    xnames += ['drdis', 'drdbetap', 'drdli', 'drdip', 'dzdis', 'dzdbetap', 'dzdli', 
      'dzdip', 'ddrsepdis', 'ddrsepdbetap', 'ddrsepdli', 'ddrsepdip', 'dpsibrydis', 
      'dpsibrydbetap', 'dpsibrydli', 'dpsibrydip', 'drxdis', 'drxdbetap', 'drxdli', 
      'drxdip', 'dzxdis', 'dzxdbetap', 'dzxdli', 'dzxdip']
    
    xnames += ['shape_' + x for x in ['drcurdix', 'dzcurdix', 'drxlodix', 'drxupdix', 'dzxlodix', 'dzxupdix', 'rcur', 'zcur', 'zx_lo_filtered', 'zx_up_filtered', 'rx_lo_filtered', 'rx_up_filtered', 'islimited']]


    train_pca = {}
    val_pca = {}
    test_pca = {}

    for xn in xnames:
        
        try:
            print('Loading ' + xn + '...')        

            trainX, trainshots, traintimes = loadX(traindir, xn, smoothit=smoothit, window=window)
            valX, valshots, valtimes = loadX(valdir, xn, smoothit=smoothit, window=window)
            testX, testshots, testtimes = loadX(testdir, xn, smoothit=smoothit, window=window)

            print('  fitting ' + xn + '...')
            pca = fit_rampup_flat_rampdown_pca(trainX, xn, trainshots, traintimes, t_rampup=t_rampup, t_rampdown=t_rampdown, evt=evt, ncomps_max=20)

            print('  measuring coefficients...')
            train_pca[xn] = eval_pca(trainX, pca)
            val_pca[xn] = eval_pca(valX, pca)
            test_pca[xn] = eval_pca(testX, pca)
        
        except:
            print('WARNING: did not fit ' + xn)
            

    train_pca['shot'] = trainshots
    train_pca['time'] = traintimes
    val_pca['shot'] = valshots
    val_pca['time'] = valtimes
    test_pca['shot'] = testshots
    test_pca['time'] = testtimes

    print('Saving model...')

    train_fn = save_dir + 'train_' + save_suffix
    val_fn = save_dir + 'val_' + save_suffix
    test_fn = save_dir + 'test_' + save_suffix

    save_data(train_pca, train_fn)
    save_data(val_pca, val_fn)        
    save_data(test_pca, test_fn)        

    print('Done')


def load(datadir, varname):
    fn = datadir + varname + '.mat'
    X = mat73.loadmat(fn)[varname]
    X = X.reshape(X.shape[0], -1)
    return X

def loadX(datadir, varname, smoothit=False, window=5):
    iuse = load(datadir, 'igood')
    iuse = np.squeeze(iuse).astype(bool)

    shot = load(datadir, 'shot')
    time = load(datadir, 'time')

    X = load(datadir, varname)
    X = X[iuse,:]
    shot = shot[iuse]
    time = time[iuse]

    if smoothit:
        X = median_filter(X, size=(window,1))
    
    return X, shot, time


def eval_pca(X, pca, smooth_coeffs=False, window=5):
    if pca is None:
        pca = EasyDict()
        pca.coeff_ = X
        return copy.deepcopy(pca)
    else:
        coeff = pca.transform(X)
        if smooth_coeffs:
            coeff = median_filter(coeff, size=(window,1))
        pca.coeff_ = coeff
        return copy.deepcopy(pca)


def fit_rampup_flat_rampdown_pca(X, xname, shots, times, t_rampup=0.1, t_rampdown=0.1, evt=0.999, ncomps_max=20):

    if X.shape[1] <= 2:
        return None
    else:

        # samples within the first t_rampup seconds of the shot (presume rampup)
        iup = np.where(times < t_rampup)[0] 
        
        # samples within the last t_rampdown seconds of the shot (presume rampdown)
        idown = []
        for shot in np.unique(shots):
            ishot = np.where(shots==shot)[0]
            shottimes = times[ishot]
            tend = max(shottimes)
            k = np.where(shottimes > tend - t_rampdown)[0]
            idown.extend(ishot[k])            
        idown = np.asarray(idown)

        # samples within the middle seconds of the shot (presume flattop)
        iflat = np.arange(len(times))
        iflat = np.setdiff1d(iflat, iup)
        iflat = np.setdiff1d(iflat, idown)

        # fit pca for each time period separately                
        pca1 = fit_pca(X[iup,:], evt=evt, ncomps_max=ncomps_max)
        pca2 = fit_pca(X[iflat,:], evt=evt, ncomps_max=ncomps_max)
        pca3 = fit_pca(X[idown,:], evt=evt, ncomps_max=ncomps_max)
        
        # merge the 3 sets of principal components into one set, then reorthogonalize
        mu = (pca1.mean_ + pca2.mean_ + pca3.mean_) / 3.0
        A = np.vstack([pca1.components_, pca2.components_, pca3.components_, mu-pca1.mean_, mu-pca2.mean_, mu-pca3.mean_])
        A = normalize(A)

        u,s,vh = np.linalg.svd(A, full_matrices=False)
        energies = np.cumsum(s) / np.sum(s)
        n_components = np.where(energies > 0.999)[0][0]+1
        n_components = min(n_components, ncomps_max)
        components = vh[:n_components, :]

        print('  final number of components used: %d ' %n_components)

        mergedPCA = PCA(n_components=n_components)
        mergedPCA.mean_ = mu
        mergedPCA.components_ = components
        mergedPCA.pca1 = pca1
        mergedPCA.pca2 = pca2
        mergedPCA.pca3 = pca3
        
    # return copy.deepcopy(pca2) 
    return copy.deepcopy(mergedPCA)

def fit_pca(X, evt, ncomps_max):

    n = min(min(X.shape), 100) - 1
    pca0 = PCA(n_components=n, svd_solver='arpack')
    pca0.fit(X)

    n_components = np.where(np.cumsum(pca0.explained_variance_ratio_) > evt)[0] + 1

    if n_components.size == 0 or n_components[0] > ncomps_max:
        n_components = ncomps_max
    else:
        n_components = n_components[0]

    evr = np.sum(pca0.explained_variance_ratio_[:n_components])
    print('  using %d components, explained variance= %.3f' %(n_components, evr))      

    pca = PCA(n_components=n_components, svd_solver='arpack')
    pca.fit(X)
    pca.explained_variance_ratio_ = pca0.explained_variance_ratio_

    return copy.deepcopy(pca)


if __name__ == '__main__':
    main()
