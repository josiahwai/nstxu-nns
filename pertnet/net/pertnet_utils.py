import numpy as np
from matplotlib import animation
from mpl_toolkits.axes_grid1 import make_axes_locatable
import matplotlib.pyplot as plt
from sklearn.preprocessing import StandardScaler
import torch.nn as nn
import torch
import scipy.io as sio
import copy

# ====================
# Train-Val-Test split
# ====================

def train_val_test_split(data_pca, ftrain=0.8, fval=0.1, ftest=0.1, mix=False):
    
    shots = data_pca['shot']
    times = data_pca['time']

    uniqshots = np.unique(shots)

    ntrain = int(ftrain*len(uniqshots))
    nval = int(fval*len(uniqshots))
    ntest = len(uniqshots) - ntrain - nval

    trainshots = uniqshots[0:ntrain]
    valshots = uniqshots[ntrain:ntrain+nval]
    testshots = uniqshots[ntrain+nval:]

    itrain = np.where(shots <= trainshots[-1])[0]
    ival = np.where( (shots >= valshots[0]) & (shots <= valshots[-1]))[0]
    itest = np.where( (shots >= testshots[0]) & (shots <= testshots[-1]))[0]

    traindata = copy.deepcopy(data_pca)
    valdata = copy.deepcopy(data_pca)
    testdata = copy.deepcopy(data_pca)

    keys = list(data_pca.keys())

    for key in keys:

        if key=='time' or key=='shot':
            traindata[key] = data_pca[key][itrain,:]
            valdata[key] = data_pca[key][ival,:]
            testdata[key] = data_pca[key][itest,:]
        else:
            traindata[key].coeff_ = data_pca[key].coeff_[itrain,:]
            valdata[key].coeff_   = data_pca[key].coeff_[ival,:]
            testdata[key].coeff_  = data_pca[key].coeff_[itest,:]

    return traindata, valdata, testdata



# =====================================
# Visualize Response Predictions
# =====================================
def visualize_response_prediction(data, preprocess, net, loss_fcn, hp, shot, nsamples=10):

    def inverse_transform(y):
        y = y.detach().numpy()
        y = preprocess.Y_scaler.inverse_transform(y)
        y = preprocess.Y_pca.inverse_transform(y)
        y = y.reshape(65, 65).T
        return y
        
    X, Y,_,_ = preprocess.transform(data, randomize=False)
    iuse = np.where(data['shot'] == shot)[0]
    iuse = np.linspace(min(iuse), max(iuse), nsamples, dtype=int)
    times = data['time'][iuse]
    X = X[iuse, :]
    Y = Y[iuse, :]
    Ypreds = net(X)

    fig = plt.figure(figsize=(20, 10))
    ax = list(range(nsamples))

    for i in range(nsamples):
        ytrue = Y[i, :]
        ypred = Ypreds[i, :]
        loss = loss_fcn(ytrue, ypred)

        psi_true = inverse_transform(ytrue)
        psi_pred = inverse_transform(ypred)

        ax[i] = fig.add_subplot(2, int(np.ceil(nsamples / 2)), i + 1)

        cs = ax[i].contour(psi_true, 20, linestyles='dashed')
        ax[i].contour(psi_pred, levels=cs.levels, linestyles='solid')
        ax[i].legend(('True', 'Prediction'))
        ax[i].set_title('t=%.3fs, Loss=%.5f' % (times[i], loss))

    fig.suptitle('Shot %d' % shot)
    fig.tight_layout(rect=[0, 0.03, 1, 0.95])

    if hp.savefigs:
        fn = hp.save_results_dir +  '/response' + str(shot) + '.png'
        plt.savefig(fn, dpi=50)


# =====================================
# Plot prediction of response pca coeff
# =====================================
def plot_response_coeffs(data, preprocess, net, hp, ncoeffs='all'):

    shotlist = np.unique(data['shot'])
    nshots = len(shotlist)

    X, Y,_,_ = preprocess.transform(data)
    if ncoeffs=='all':
        ncoeffs = Y.shape[1]

    for icoeff in range(ncoeffs):

        fig = plt.figure(figsize=(20, 10))
        ax = list(range(nshots))

        for ishot, shot in enumerate(shotlist):
            i = np.where(data['shot'] == shot)[0]
            t = data['time'][i]
            X, Y,_,_ = preprocess.transform(data, randomize=False)
            X = X[i, :]
            Y = Y[i, :]
            Ypred = net(X).detach().numpy()

            ax[ishot] = fig.add_subplot(4, int(np.ceil(nshots / 4)), ishot + 1)
            ax[ishot].plot(t, Y[:, icoeff], linestyle='dashed')
            ax[ishot].plot(t, Ypred[:, icoeff])
            ax[ishot].set_title(shot)

        fig.suptitle('PCA Coeff %d' % (icoeff + 1))
        fig.tight_layout(rect=[0, 0.03, 1, 0.95])

        if hp.savefigs:
            fn = hp.save_results_dir +  '/coeff' + str(icoeff) + '.png'
            plt.savefig(fn, dpi=50)


# ===============
# Plot loss curve
# ===============
def plot_loss_curve(training_loss, validation_loss, hp):

    plt.figure()
    plt.semilogy(training_loss)
    plt.semilogy(validation_loss)
    plt.xlabel('Iteration')
    plt.ylabel('Training loss')
    if hp.savefigs:
        fn = hp.save_results_dir +  '/loss_curve.png'
        plt.savefig(fn, dpi=50)


# ===========================
# Make movie of shot response
# ===========================
def make_shot_response_movie(data, preprocess, net, loss_fcn, hp, ishot=0):

    def inverse_transform(y):
        y = y.detach().numpy()
        y = preprocess.Y_scaler.inverse_transform(y)
        y = preprocess.Y_pca.inverse_transform(y)
        y = y.reshape(65, 65).T
        return y

    shotlist = np.unique(data['shot'])
    shot = shotlist[ishot]
    X, Y,_,_ = preprocess.transform(data, randomize=False)
    iuse = np.where(data['shot'] == shot)[0]
    Nplots = min(20, len(iuse))
    iuse = np.linspace(min(iuse), max(iuse), Nplots, dtype=int)
    times = data['time'][iuse]
    X = X[iuse, :]
    Y = Y[iuse, :]
    Ypreds = net(X)

    fig, ax = plt.subplots(1, 2, figsize=(6, 6))
    div = make_axes_locatable(ax[1])
    cax = div.append_axes('right', '5%', '5%')

    def animate(i):

        ytrue = Y[i, :]
        ypred = Ypreds[i, :]
        loss = loss_fcn(ytrue, ypred)

        psi_true = inverse_transform(ytrue)
        psi_pred = inverse_transform(ypred)

        psi_min = min(psi_pred.min(), psi_true.min())
        psi_max = max(psi_pred.max(), psi_true.max())
        levels = np.linspace(psi_min, psi_max, 30)

        ax[0].cla()
        ax[0].set_title('True')
        cs = ax[0].contourf(psi_true, levels=levels)
        ax[0].contour(psi_true, levels=levels, linewidths=0.5, colors='k')

        ax[1].cla()
        ax[1].set_title('Prediction')
        ax[1].contourf(psi_pred, levels=levels)
        ax[1].contour(psi_pred, levels=levels, linewidths=0.5, colors='k')

        cax.cla()
        fig.colorbar(cs, cax=cax)
        fig.suptitle('Shot %d, Time %.3f, Loss %.5f' % (shot, times[i], loss))
        cs.set_clim(vmin=levels.min(), vmax=levels.max())

        fig.tight_layout(rect=[0, 0.03, 1, 0.95])

    anim = animation.FuncAnimation(fig, animate, frames=range(len(times)), interval=50)

    if hp.savemovie:
        anim.save('./response_movie.mp4', fps=10, dpi=50)

    return anim


# ========
# TRAINING
# ========
def train(net, loss_fcn, optimizer, train_dataloader, val_dataloader, hp):

    training_loss = []
    validation_loss = []
    val_dataiter = iter(val_dataloader)

    for epoch in range(hp.num_epochs):
        for i, data in enumerate(train_dataloader):

            x_batch, y_batch = data
            y_pred = net(x_batch)

            # compute loss
            loss = loss_fcn(y_pred, y_batch)

            # update parameters
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            batch_loss = loss.item()

            if i % hp.print_every == 0:

                # save training loss
                training_loss.append(batch_loss)

                # calculate and save validation loss
                try:
                    x, y = val_dataiter.next()
                except StopIteration:
                    val_dataiter = iter(val_dataloader)
                    x, y = val_dataiter.next()
                
                net.eval()
                with torch.no_grad():
                    ypred = net(x)
                    val_loss = loss_fcn(ypred, y).item()
                    validation_loss.append(val_loss)
                net.train()

                print('Epoch: %d of %d, train_loss: %3e, val_loss: %3e' %
                      (epoch + 1, hp.num_epochs, batch_loss, val_loss))

    return net, training_loss, validation_loss


# ==============
# LOSS FUNCTIONS
# ==============
def mse_loss(input, target):
    return torch.mean((input - target) ** 2)

def weighted_mse_loss(input, target, weight=None):
    return torch.mean(weight * (input - target) ** 2)

def LMLS(input, target):
    return torch.mean(torch.log(1 + 0.5 * (input - target)**2))

class Weighted_MSE_Loss():
    def __init__(self, weights):
        super().__init__()
        self.weights = weights
    def loss(self, input, target):
        return torch.mean(self.weights * (input-target)**2)

class PLoss():
    def __init__(self, p=2):
        super().__init__()
        self.p = p
    def loss(self, input, target):
        eps = 1e-12
        e = torch.abs(input-target) + eps
        loss = torch.mean(e**self.p)
        return loss

# ===========================
# MULTILAYER PERCEPTRON CLASS
# ===========================
class MLP(nn.Module):
    '''
    Multilayer Perceptron.
    '''

    def __init__(self, in_dim, out_dim, hidden_dims, nonlinearity='RELU', p_dropout_in=0, p_dropout_hidden=0.2):
        super().__init__()
        
        if nonlinearity.upper() == 'RELU':
            nonlinearity = nn.ReLU()
        elif nonlinearity.upper() == 'TANH':
            nonlinearity = nn.Tanh()
        elif nonlinearity.upper() == 'LEAKYRELU':
            nonlinearity = nn.LeakyReLU()
        elif nonlinearity.upper() == 'ELU':
            nonlinearity = nn.ELU()
        
        dims = [in_dim]
        dims.extend(hidden_dims)
        dims.extend([out_dim])

        nlayers = len(dims) - 1
        layers = []

        for i in range(nlayers):
            if i == 0:
                p = p_dropout_in
            else:
                p = p_dropout_hidden
            layers.append(nn.Dropout(p=p))
            layers.append(nn.Linear(dims[i], dims[i + 1]))
            layers.append(nonlinearity)

        layers.pop()
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x)


'''
# ==================
# DATA PREPROCESSING
# ==================
class DataPreProcess():
    def __init__(self, datadict, xnames, ynames, t_thresh=None):
        super().__init__()

        X = self.makeX(datadict, xnames)
        X_scaler = StandardScaler()
        X_scaler.fit(X)

        Y = self.makeX(datadict, ynames)
        Y_scaler = StandardScaler()
        Y_scaler.fit(Y)

        # write to class object
        self.X_scaler = X_scaler
        self.Y_scaler = Y_scaler
        self.Y_pca = datadict[ynames[0]]
        self.t_thresh = t_thresh        
        self.xnames = xnames
        self.ynames = ynames

    def makeX(self, datadict, xnames):

        for i, key in enumerate(xnames):

            try:
                x = datadict[key].coeff_
            except:
                x = datadict[key]

            if i == 0:
                Xdata = np.copy(x)
            else:
                Xdata = np.hstack([Xdata, x])

        return Xdata

    def transform(self, datadict, randomize=True, holdback_fraction=0.0):

        X = self.makeX(datadict, self.xnames)
        Y = self.makeX(datadict, self.ynames)

        X = self.X_scaler.transform(X)
        Y = self.Y_scaler.transform(Y)

        time = datadict['time']
        shot = datadict['shot']

        # use only certain times
        if self.t_thresh is not None:
            t = datadict['time']
            iuse = np.where(t > self.t_thresh)[0]
            X = X[iuse, :]
            Y = Y[iuse, :]
            time = time[iuse]
            shot = shot[iuse]
        
        # remove samples with nans
        i = ~np.isnan(X).any(axis=1) & ~np.isnan(Y).any(axis=1)
        X = X[i,:]
        Y = Y[i,:]
        time = time[i]
        shot = shot[i]

        # convert to torch data types
        X = torch.Tensor(X)
        Y = torch.Tensor(Y)

        # randomize order
        if randomize:
            idx = torch.randperm(X.shape[0])
            X = X[idx, :]
            Y = Y[idx, :]
            time = time[idx]
            shot = shot[idx]

        # hold back some samples
        nsamples = X.shape[0]
        nkeep = int((1.0 - holdback_fraction)*nsamples)
        X = X[:nkeep,:]
        Y = Y[:nkeep,:]
        time = time[:nkeep]
        shot = shot[:nkeep]

        return X, Y, shot, time

'''


# ==================
# DATA PREPROCESSING
# ==================
class DataPreProcess():
    def __init__(self, datadict, xnames, ynames, t_thresh=None):
        super().__init__()

        X = self.makeX(datadict, xnames)
        X_scaler = StandardScaler()
        X_scaler.fit(X)

        Y = self.makeX(datadict, ynames)
        Y_scaler = StandardScaler()
        Y_scaler.fit(Y)

        # write to class object
        self.X_scaler = X_scaler
        self.Y_scaler = Y_scaler
        self.Y_pca = datadict[ynames[0]]
        self.t_thresh = t_thresh        
        self.xnames = xnames
        self.ynames = ynames

    def makeX(self, datadict, xnames):

        for i, key in enumerate(xnames):

            try:
                x = datadict[key].coeff_
            except:
                x = datadict[key]

            if i == 0:
                Xdata = np.copy(x)
            else:
                Xdata = np.hstack([Xdata, x])

        return Xdata

    def transform(self, datadict, randomize=True, holdback_fraction=0.0, by_shot=False):

        X = self.makeX(datadict, self.xnames)
        Y = self.makeX(datadict, self.ynames)

        X = self.X_scaler.transform(X)
        Y = self.Y_scaler.transform(Y)

        time = datadict['time']
        shot = datadict['shot']

        # use only certain times
        if self.t_thresh is not None:
            t = datadict['time']
            iuse = np.where(t > self.t_thresh)[0]
            X = X[iuse, :]
            Y = Y[iuse, :]
            time = time[iuse]
            shot = shot[iuse]
        
        # remove samples with nans
        i = ~np.isnan(X).any(axis=1) & ~np.isnan(Y).any(axis=1)
        X = X[i,:]
        Y = Y[i,:]
        time = time[i]
        shot = shot[i]

        if holdback_fraction > 0 and by_shot:
            uniqshots = np.unique(shot)
            sz = int( (1.0-holdback_fraction)*len(uniqshots))
            select_shots = np.random.choice(uniqshots, sz, replace=False)
            
            for ishot, select_shot in enumerate(select_shots):
                
                k = np.where(shot == select_shot)[0]
                if ishot==0:
                    idx = k
                else:
                    idx = np.hstack((idx,k))
            
            X = X[idx,:]
            Y = Y[idx,:]
            time = time[idx]
            shot = shot[idx]

        # convert to torch data types
        X = torch.Tensor(X)
        Y = torch.Tensor(Y)


        # randomize order
        if randomize:
            idx = torch.randperm(X.shape[0])
            X = X[idx, :]
            Y = Y[idx, :]
            time = time[idx]
            shot = shot[idx]


        # hold back some samples
        if holdback_fraction > 0 and not by_shot:
            nsamples = X.shape[0]
            nkeep = int((1.0 - holdback_fraction)*nsamples)
            X = X[:nkeep,:]
            Y = Y[:nkeep,:]
            time = time[:nkeep]
            shot = shot[:nkeep]

        return X, Y, shot, time





# ==================
# Growth rate calcs
# ==================
class GrowthRate():
    
    def __init__(self, geometry_files_dir):
        
        self.M = sio.loadmat(geometry_files_dir + '/M.mat')['M']
        self.MpcMpv = sio.loadmat(geometry_files_dir + '/MpcMpv.mat')['MpcMpv']
        self.Mpp = sio.loadmat(geometry_files_dir + '/Mpp.mat')['Mpp']
        self.Pxx = sio.loadmat(geometry_files_dir + '/Pxx.mat')['Pxx']
        self.Rxx = sio.loadmat(geometry_files_dir + '/Rxx.mat')['Rxx']
        self.Mppi = np.linalg.inv(self.Mpp)
    
    def calc_gamma(self, dpsidix_shot):
        
        nsamples = dpsidix_shot.shape[0]
        gamma = np.zeros(nsamples)
        
        for i in range(nsamples):
            
            dpsidix = dpsidix_shot[i,:,:]
            dcphidix = self.Mppi @ dpsidix
            X = self.Pxx.T @ self.MpcMpv.T @ dcphidix
            amat = -np.linalg.inv(self.M + X) @ self.Rxx
            e, _ = np.linalg.eig(amat)
            max_eig = np.max(np.real(e))
            gamma[i] = max_eig
        
        return gamma           

# ======================
# plot response timetraces
# ======================
def plot_response_timetraces(shotlist, net, valdata, preprocess,hp):
    
    X,Ytrue,shots,times = preprocess.transform(valdata, randomize=False, holdback_fraction=0)
    Ypred = net(X).detach().numpy()            
    
    def readY(Y, preprocess, hp):
        Y = preprocess.Y_scaler.inverse_transform(Y)  # denormalize
        Ydict = {}
        istart = 0
        for yname in hp.ynames:        
            istop = istart + valdata[yname].coeff_.shape[1]
            Ydict[yname] = Y[:, istart:istop]
            istart = istop
            # try:
            #     pca = valdata[yname]
            #     Ydict[yname] = pca.inverse_transform(Ydict[yname]) # inverse pca
            # except:
            #     continue

        return Ydict
    
    Ytrue = readY(Ytrue,preprocess,hp)  
    Ypred = readY(Ypred,preprocess,hp)

    
    # make plots
    for shot in shotlist:
        i = np.where(shots==shot)[0]
        fig = plt.figure(figsize=(16, 10))
        ax = list(range(len(hp.ynames)))

        for iax, yname in enumerate(hp.ynames):
            ax[iax] = fig.add_subplot(4, 5, iax+1)
            n = min(3, Ytrue[yname].shape[1]) # only plot a few modes, if multivariate
            ax[iax].plot( times[i], Ytrue[yname][i,:n], c='r', linestyle='dashed')
            ax[iax].plot( times[i], Ypred[yname][i,:n], c='b', linestyle='dashed')    
            ax[iax].set_ylabel(yname)
            ax[iax].set_xlabel('Time [s]')
            ymax = 10*np.median(np.abs(Ytrue[yname][i,:n]))
            ymax = min(ymax, np.max(Ytrue[yname][i,:n]))
            ymin = max(-ymax, np.min(Ytrue[yname][i,:n]))
            ax[iax].set_ylim((ymin,ymax))

        fig.suptitle('Shot %d' % shot)
        fig.tight_layout(rect=[0, 0.03, 1, 0.95])   

        if hp.savefigs:
            fn = hp.save_results_dir +  '/traces' + str(shot) + '.png'
            plt.savefig(fn, dpi=100)
