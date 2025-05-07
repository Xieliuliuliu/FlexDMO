import numpy as np
import random
import math

def LocalPCA(PopDec, M, K):
    N, D = np.shape(PopDec)  # Dimensions
    Model = [{'mean': PopDec[k],  # The mean of the model
              'PI': np.eye(D),  # The matrix PI
              'eVector': [],  # The eigenvectors
              'eValue': [],  # The eigenvalues
              'a': [],  # The lower bound of the projections
              'b': []} for k in range(K)]  # The upper bound of the projections

    ## Modeling
    iter = 1
    update = K
    repartion = 1
    total = 0
    while((iter <= 200 and update > 0) or (repartion > 0)):
        total = total + 1
        if(total > 200):
            break
        # Calculte the distance between each solution and its projection in
        # affine principal subspace of each cluster
        distance = np.zeros((N, K))  # matrix of zeros N*K
        for k in range(K):
            distance[:, k] = np.sum(np.dot((PopDec - np.tile(Model[k]['mean'], (N, 1))), Model[k]['PI']) * (
                        PopDec - np.tile(Model[k]['mean'], (N, 1))), axis=1)

        # Partition
        partition = np.argmin(distance, axis=1)
        id = np.eye(K)
        cindex = id[partition,:]

        update = K
        repartion = 0

        for k in range(K):
            oldmean = Model[k]['mean'].copy()
            if(sum(cindex[:,k]) < 1):
                index = random.sample(range(N), 1)
                Model[k]['mean'] = PopDec[index,:]
                Model[k]['PI'] = np.eye(D)
                repartion = 1
            elif(sum(cindex[:,k]) == 1):
                Model[k]['mean'] = PopDec[cindex[:,k]>0,:]
                Model[k]['PI'] = np.eye(D)
            else:
                cx = PopDec[cindex[:,k]>0,:]
                count, temp = np.shape(cx)
                Model[k]['mean'] = np.mean(cx, 0)
                mean_matrix = np.tile(Model[k]['mean'], [count, 1])
                cy = cx - mean_matrix
                eva, eve = np.linalg.eig(np.cov(np.transpose(cy)))
                rank = np.argsort(-eva)
                eva = -np.sort(-eva)
                eve = eve[:,rank]
                Model[k]['eVector'] = eve
                Model[k]['eValue'] = eva
                Model[k]['PI'] = np.dot(eve[:,(M-1):D], np.transpose(eve[:,(M-1):D]))

            err = math.sqrt(np.sum((oldmean - Model[k]['mean']) * (oldmean - Model[k]['mean'])))
            if(err < 1e-5):
                update = update - 1

        iter = iter + 1

    for k in range(K):
        Model[k]['eValue'] = np.real(Model[k]['eValue'])
        Model[k]['eVector'] = np.real(Model[k]['eVector'])
        Model[k]['PI'] = np.real(Model[k]['PI'])
        Model[k]['mean'] = np.real(Model[k]['mean'])

    ## Calculate the smallest hyper-rectangle of each model
    exist = np.zeros(K)
    for k in range(K):
        if sum(cindex[:,k]) > 1:
            exist[k] = 1
            hyperRectangle = (PopDec[partition == k, :] - np.tile(Model[k]['mean'], (sum(partition == k), 1))).dot(
                Model[k]['eVector'][:, 0:M - 1])
            Model[k]['a'] = np.min(hyperRectangle, axis=0)
            Model[k]['b'] = np.max(hyperRectangle, axis=0)
        else:
            exist[k] = 0
            Model[k]['a'] = np.zeros((1, M - 1))
            Model[k]['b'] = np.zeros((1, M - 1))

    ## Calculate the probability of each cluster for reproduction
    volume = np.ones([1,K])
    for i in range(K):
        volume[0,i] = np.prod(Model[i]['b'] - Model[i]['a'])
    volume = (volume + 0.0000001) * exist
    # Calculate the cumulative probability of each cluster
    probability = volume / np.sum(volume)
    cn = 2*np.ones([1,K]) + np.floor((N - 2*K)*probability)
    while(np.sum(cn) < N):
        temp = np.sort(cn)
        for k in range(K):
            if(temp[0,k] > 2):
                num = temp[0,k]
                break
        id = np.where(cn == num)[1][0]
        cn[0,id] = cn[0,id] + 1

    return Model, cn 