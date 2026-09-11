# Generated reference M1; only infimal convolution is native.
import numpy as np
from scipy.spatial.distance import cdist
from control import EMIN, EMAX
from nextgen_control import terminal_values, nonnegative_kernel, minimize_action
from native import inf_convolution
class EnhancedMarkovDP:
    """Origin-conditioned VAR + empirical innovations, convex inventory chords.

    External states use scenario support with nonnegative kernel interpolation.
    This is an approximate finite-support kernel, not a true-process lower bound.
    Current price is integrated before choosing the physical action.
    """
    def __init__(self, bundle, q, asof, config, tail_price, terminal=None, tail_cuts=None):
        net, prices, states, weights = (bundle[k] for k in ('net', 'prices', 'states', 'weights'))
        S, T = net.shape; D = states.shape[2]; self.grid = np.linspace(EMIN, EMAX, config.grid)
        self.support = states; self.weights = weights; self.variable = D == 4
        self.future = np.empty((T, S, config.grid)); self.price = np.empty((T, S))
        self.models = []; self.alpha = config.alpha; self.forecast_price = bundle['forecast']['price']
        hx = bundle['history_states']; rn, rp = bundle['history_net_error'], bundle['history_price_error']
        X = hx[:, :-1].reshape(-1, D)
        Y = np.stack((rn[:, 1:], rp[:, :-1]), axis=2).reshape(-1, 2) if self.variable else rn[:, 1:].reshape(-1, 1)
        phases = ((bundle['origins'][:, None]+np.arange(T-1)) % 144//36).ravel()
        scales = np.std(X, axis=0)
        # Each error and corresponding EMA share a scale to preserve the EMA algebra.
        scales[:2] = max(float(np.std(rn)), 1e-8)
        if self.variable: scales[2:] = max(float(np.std(rp)), 1e-8)
        self.scales = scales
        for phase in range(4):
            ids = np.flatnonzero(phases == phase)
            if not len(ids): ids = np.arange(len(X))
            design = np.c_[np.ones(len(ids)), X[ids]/scales]
            regularizer = np.diag(np.r_[0., np.full(D, config.ridge*len(ids))])
            coefficients = np.linalg.solve(design.T@design+regularizer, design.T@Y[ids])
            residuals = Y[ids]-design@coefficients
            # Deterministic farthest-first representatives, masses assigned by nearest
            # empirical innovation. Actual historical residuals, never Gaussian draws.
            residual_scale = np.maximum(residuals.std(0), 1e-8)
            standardized = residuals/residual_scale
            chosen = [int(np.argmin(np.sum(standardized**2, axis=1)))]; distance = np.sum((standardized-standardized[chosen[0]])**2, axis=1)
            for _ in range(min(config.innovation_count, len(ids))-1):
                ix = int(np.argmax(distance))
                if distance[ix] < 1e-14: break
                chosen.append(ix); distance = np.minimum(distance, np.sum((standardized-standardized[ix])**2, axis=1))
            labels = np.argmin(cdist(standardized, standardized[chosen]), axis=1)
            mass = np.bincount(labels, minlength=len(chosen))/len(labels)
            selected = residuals[chosen]; mean_error = mass@selected
            # Keep unshifted empirical innovations; report reduced-measure mean error.
            a = coefficients[1:].T/scales[None]; b = coefficients[0]
            A = np.empty((D, D)); intercept = np.empty(D)
            A[0] = a[0]; A[1] = config.alpha*a[0]; A[1, 1] += 1-config.alpha
            intercept[:2] = b[0], config.alpha*b[0]
            if self.variable:
                A[2] = a[1]; A[3] = config.alpha*a[1]; A[3, 3] += 1-config.alpha
                intercept[2:] = b[1], config.alpha*b[1]
            self.models.append({'A': A, 'b': intercept, 'innovations': selected, 'mass': mass,
                                'rows': len(ids), 'reduced_innovation_mean': mean_error})
        v = np.tile(terminal_values(self.grid, tail_price, terminal, tail_cuts), (S, 1))
        for j in range(T-1, -1, -1):
            phase = (asof+j) % 144//36
            nxt, mean_price = self.transition(states[:, j], phase, self.forecast_price[j])
            self.price[j] = mean_price
            if j == T-1:
                future = np.tile(v[0], (S, 1))
            else:
                model = self.models[phase]; kernels = nonnegative_kernel(states[:, j+1], nxt.reshape(-1, D), scales, weights)
                P = np.einsum('sik,i->sk', kernels.reshape(S, -1, S), model['mass'])
                future = P@v
            self.future[j] = future
            # Collocate the SAME continuous kernel used by action(). A Gaussian
            # kernel is not cardinal: even at a support point it mixes neighbors.
            # Applying it only online would define a different greedy policy.
            support_kernel = nonnegative_kernel(states[:, j], states[:, j], scales, weights)
            collocated_future = support_kernel@future
            collocated_price = support_kernel@mean_price
            v = np.array([inf_convolution(self.grid, collocated_future[s], net[s, j]-q[j], collocated_price[s]) for s in range(S)])
        self.initial_values = v
        self.asof = asof

    def transition(self, x, phase, baseline_price):
        x = np.atleast_2d(x); model = self.models[phase]; innovation = model['innovations']
        predicted = x@model['A'].T+model['b']
        next_state = np.repeat(predicted[:, None], len(innovation), axis=1)
        next_state[:, :, 0] += innovation[:, 0]; next_state[:, :, 1] += self.alpha*innovation[:, 0]
        if self.variable:
            error = predicted[:, None, 2]+innovation[None, :, 1]
            price = np.maximum(.001, baseline_price+error)
            error = price-baseline_price
            next_state[:, :, 2] = error
            next_state[:, :, 3] = (1-self.alpha)*x[:, None, 3]+self.alpha*error
            mean_price = price@model['mass']
        else:
            mean_price = np.full(len(x), baseline_price)
        return next_state, mean_price

    def action(self, j, E, net, q, state):
        w = nonnegative_kernel(self.support[:, j], state, self.scales, self.weights)[0]
        # The same nonnegative interpolation defines the declared approximate kernel
        # and its continuation value; coefficients never depend on inventory.
        future = w@self.future[j]
        price = float(w@self.price[j])
        return minimize_action(self.grid, future, E, net-q, price)

    def diagnostics(self):
        return {'model': 'origin-conditioned empirical VAR with convex inventory interpolation',
                'scale': self.scales.tolist(), 'phases': [
                    {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in model.items()}
                    for model in self.models]}
