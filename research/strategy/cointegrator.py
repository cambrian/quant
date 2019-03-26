from strategy import Strategy
from util.gaussian import Gaussian

import numpy as np
import pandas as pd
from numpy_ringbuffer import RingBuffer
from .johansen.johansen import Johansen
from math import sqrt, log1p


def cointegrate(data):
    '''Returns eigenvectors for statistically-significant cointegration relations.
    TODO: return confidences, by using eigenvalues directly.'''
    eigenvectors, r = Johansen(data, model=2, significance_level=1).johansen()
    return np.array(eigenvectors)[r]


def plot_eigenvectors(evs):
    evs /= np.linalg.norm(evs, axis=1, keepdims=True)
    plot_matrix(pd.DataFrame(evs))


class CointegratorStrategy(Strategy):
    def __init__(self, cointegration_window_size):
        '''Edges are expressed in standard deviations of the currency price. Size is expressed in
        $ per stdev of edge.'''
        self.cointegration_window = None
        self.cointegration_window_size = cointegration_window_size

    def step(self, prices, _volumes):
        if self.cointegration_window is None:
            self.cointegration_window = RingBuffer(
                self.cointegration_window_size, dtype=(np.float, len(prices.index)))

        self.cointegration_window.append(prices)

        if len(self.cointegration_window) < self.cointegration_window_size:
            return self.null_estimate(prices)

        df = pd.DataFrame(np.array(self.cointegration_window), columns=prices.index)

        relations = cointegrate(df)
        fairs = []  # 1 fair estimate per covariance relation
        for relation in relations:
            R = np.broadcast_to(relation, (prices.shape[0], prices.shape[0])).copy()
            R /= np.diag(R)[:None]
            np.fill_diagonal(R, 0)
            synth_cointegrations = pd.DataFrame(df.values.dot(R), columns=df.columns)
            fair_mean = prices + synth_cointegrations.iloc[-1] - synth_cointegrations.mean()
            fair_variance = synth_cointegrations.var()
            fairs.append(Gaussian(fair_mean, fair_variance))
        if len(fairs) > 0:
            return Gaussian.join(fairs)
        else:
            return self.null_estimate(prices)
