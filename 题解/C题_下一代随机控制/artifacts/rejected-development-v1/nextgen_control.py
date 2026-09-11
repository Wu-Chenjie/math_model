"""Probability-consistent causal affine planning and convex value feedback."""
import time
import numpy as np
from scipy.sparse import coo_matrix, vstack, eye, diags
from scipy.spatial.distance import cdist
from control import ETA, M, EMIN, EMAX, lp_solve, inf_convolution, MarkovDP, affine_plan as legacy_affine_plan
from nextgen_scenarios import weighted_quantile


def affine_plan(bundle, asof, inventory, config, base=None, adjust=False,
                tail_price=0., terminal=None, tail_cuts=None):
    started = time.perf_counter()
    net, prices, weights = (bundle[k] for k in ('net', 'prices', 'weights'))
    S, T = net.shape; K = S*T; clock = np.arange(asof, asof+T)
    if config.upper == 'legacy' and config.alpha == .2 and config.gain_bound == 10. and np.all(weights == 1/S):
        if tail_cuts and (asof+T) % 144:
            raise ValueError('Existing SDDP inventory cuts require midnight')
        answer = legacy_affine_plan(net, prices, asof, inventory, base, adjust, True, tail_price, terminal, tail_cuts)
        active = answer.pop('gain_active_columns'); gains = answer.pop('all_gain')
        answer.update({'runtime_seconds': time.perf_counter()-started,
                       'gain_active_count': int(active.sum()),
                       'gain_bound_hit_count': int(np.sum((np.abs(gains)>=10*(1-1e-6)) & active)),
                       'gain_max_abs': float(np.max(np.abs(gains[active]), initial=0)),
                       'contract_information_cutoffs': {'original': (clock//144*144).tolist(), 'effective': (clock//36*36 if adjust else clock//144*144).tolist()},
                       'future_partial_contract_completion': 'outside-core suffix fixed to nonnegative origin forecast, no tail delivery cost'})
        return answer
    blocks = clock//36-clock[0]//36; B = int(blocks.max()+1)
    days = clock//144-asof//144; D = int(days.max()+1)
    if config.upper == 'legacy':
        error = net-weights@net; ema = np.empty_like(error); avg = np.empty_like(error)
        z = np.zeros(S)
        for j in range(T):
            z = (1-config.alpha)*z+config.alpha*error[:, j]; ema[:, j] = z
            avg[:, j] = error[:, max(0, j-35):j+1].mean(1)
        energy_features = np.stack((error, ema), axis=2)
        previous_features = np.stack((avg, ema), axis=2)
    elif config.upper == 'state':
        energy_features = bundle['states'].copy()
        previous_features = energy_features.copy()
        if energy_features.shape[-1] == 4:
            # Battery state has p_(t-1); next release may use the newly disclosed p_t.
            ep = prices-bundle['forecast']['price']
            zp = np.full(S, bundle['seed'][3])
            for j in range(T):
                zp = (1-config.alpha)*zp+config.alpha*ep[:, j]
                previous_features[:, j, 2:] = np.c_[ep[:, j], zp]
            scale = max(float(np.std(bundle['history_net_error'])), 1e-8)/max(float(np.std(bundle['history_price_error'])), 1e-8)
            energy_features[:, :, 2:] *= scale; previous_features[:, :, 2:] *= scale
        energy_features -= np.einsum('s,std->td', weights, energy_features)
        previous_features -= np.einsum('s,std->td', weights, previous_features)
    else:
        raise ValueError(config.upper)
    Fdim = energy_features.shape[2]
    aq = 0; ar = T; ae = 2*T; gq = 3*T; gr = gq+Fdim*D
    ge = gr+Fdim*B; em = ge+Fdim*B; bill = em+K; theta = bill+K
    N = theta+(S if tail_cuts else 0)

    def expression(which):
        rows, cols, values = [], [], []; constant = np.zeros(K)
        for s in range(S):
            for j, ts in enumerate(clock):
                row = s*T+j; di = days[j]; bi = blocks[j]
                if which == 'Q' and di == 0 and base is not None:
                    constant[row] = base[j]; continue
                if which == 'Q':
                    intercept, gain, reveal = aq+j, gq+Fdim*di, ts//144*144-asof
                elif which == 'R':
                    intercept, gain, reveal = ar+j, gr+Fdim*bi, ts//36*36-asof
                else:
                    intercept, gain, reveal = ae+j, ge+Fdim*bi, j+1
                rows.append(row); cols.append(intercept); values.append(1.)
                if reveal > 0:
                    feature = energy_features[s, j] if which == 'E' else previous_features[s, reveal-1]
                    for k, value in enumerate(feature):
                        rows.append(row); cols.append(gain+k); values.append(value)
        return coo_matrix((values, (rows, cols)), shape=(K, N)).tocsr(), constant

    Q, q0 = expression('Q'); R, r0 = expression('R') if adjust else (Q, q0)
    X, _ = expression('E')
    if adjust:
        first = np.tile(clock % 144 < 36, S).astype(float); keep = diags(first)
        R = keep@Q+(eye(K)-keep)@R; r0 = first*q0+(1-first)*r0
    shift = coo_matrix((np.ones(S*(T-1)),
        (np.concatenate([np.arange(s*T+1, (s+1)*T) for s in range(S)]),
         np.concatenate([np.arange(s*T, (s+1)*T-1) for s in range(S)]))), shape=(K, K)).tocsr()
    Delta = X-shift@X; delta0 = np.zeros(K); delta0[np.arange(S)*T] = -inventory
    U = coo_matrix((np.ones(K), (np.arange(K), em+np.arange(K))), shape=(K, N)).tocsr()
    C = coo_matrix((np.ones(K), (np.arange(K), bill+np.arange(K))), shape=(K, N)).tocsr()
    mats = [-Q, -R, X, -X, Delta, -Delta, ETA*Delta-R-U, Delta/ETA-R-U,
            1.5*R-.5*Q-C, .5*R+.5*Q-C]
    rhs = [q0, r0, np.full(K, EMAX), np.full(K, -EMIN),
           np.full(K, ETA*M)-delta0, np.full(K, M/ETA)+delta0,
           r0-net.ravel()-ETA*delta0, r0-net.ravel()-delta0/ETA,
           .5*q0-1.5*r0, -.5*q0-.5*r0]
    last = np.arange(S)*T+T-1
    if terminal is not None:
        mats += [X[last], -X[last]]; rhs += [np.full(S, terminal), np.full(S, -terminal)]
    if tail_cuts:
        if (asof+T) % 144:
            raise ValueError('Existing inventory-only SDDP cuts require a midnight contract-reset interface')
        Theta = coo_matrix((np.ones(S), (np.arange(S), theta+np.arange(S))), shape=(S, N)).tocsr()
        for intercept, slope in tail_cuts:
            mats.append(slope*X[last]-Theta); rhs.append(np.full(S, -intercept))
    obj = np.zeros(N); obj[em:bill] = (5*prices*weights[:, None]).ravel()
    obj[bill:theta] = (prices*weights[:, None]).ravel()
    if tail_cuts:
        obj[theta:] = weights
    obj -= tail_price*np.asarray(weights@X[last]).ravel()
    bounds = [(None, None)]*(3*T)+[(-config.gain_bound, config.gain_bound)]*(Fdim*(D+2*B))+[(0, None)]*(2*K+(S if tail_cuts else 0))
    sol = lp_solve(obj, vstack(mats), np.concatenate(rhs), bounds)
    qs = (Q@sol.x+q0).reshape(S, T); rs = (R@sol.x+r0).reshape(S, T)
    xs = (X@sol.x).reshape(S, T); delta = xs-np.c_[np.full(S, inventory), xs[:, :-1]]
    emergency = np.maximum(net-rs+np.maximum(ETA*delta, delta/ETA), 0)
    bills = np.sum(prices*(np.maximum(1.5*rs-.5*qs, .5*rs+.5*qs)+5*emergency), axis=1)
    recomputed = float(weights@(bills-tail_price*xs[:, -1]))
    if tail_cuts:
        recomputed += float(weights@np.maximum(0, np.max([a+b*xs[:, -1] for a, b in tail_cuts], axis=0)))
    gains = sol.x[gq:em]; bound_hit = np.abs(gains) >= config.gain_bound*(1-1e-6)
    # Inactive root-node gains do not count toward the binding-frequency denominator.
    active_columns = np.asarray(abs(vstack(mats)[:, gq:em]).sum(axis=0)).ravel() > 1e-12
    return {'q': weights@qs, 'r': weights@rs, 'scenario_q': qs, 'scenario_r': rs,
            'scenario_state': xs, 'lp_violation': sol.violation,
            'objective_gap': abs(recomputed-sol.fun), 'objective': sol.fun,
            'runtime_seconds': time.perf_counter()-started,
            'gain_active_count': int(active_columns.sum()),
            'gain_bound_hit_count': int(np.sum(bound_hit & active_columns)),
            'gain_max_abs': float(np.max(np.abs(gains[active_columns]), initial=0)),
            'contract_information_cutoffs': {'original': (clock//144*144).tolist(),
                                             'effective': (clock//36*36 if adjust else clock//144*144).tolist()},
            'future_partial_contract_completion': 'outside-core suffix fixed to nonnegative forecast from this origin; suffix delivery costs omitted by inventory-tail truncation'}


class WeightedMarkovDP:
    def __init__(self, net, prices, q, weights, tail_price, grid_size=321, bins=3, terminal=None, tail_cuts=None):
        self.legacy = None
        if bins == 3 and np.allclose(weights, 1/len(weights), rtol=0, atol=1e-15):
            self.legacy = MarkovDP(net, prices, q, tail_price, grid_size, terminal, tail_cuts)
            return
        S, T = net.shape; self.grid = np.linspace(EMIN, EMAX, grid_size)
        self.cuts = np.array([weighted_quantile(net[:, j], np.arange(1, bins)/bins, weights) for j in range(T)])
        labels = np.sum(net[:, :, None] > self.cuts[None], axis=2)
        self.future = np.empty((T, bins, grid_size)); self.price = np.empty((T, bins))
        v = np.tile(terminal_values(self.grid, tail_price, terminal, tail_cuts), (bins, 1))
        for j in range(T-1, -1, -1):
            counts = np.zeros((bins, bins))
            if j < T-1:
                np.add.at(counts, (labels[:, j], labels[:, j+1]), S*weights)
            P = (counts+1/bins)/(counts.sum(1, keepdims=True)+1)
            nxt = P@v; self.future[j] = nxt; cur = np.empty_like(v)
            for k in range(bins):
                ids = np.flatnonzero(labels[:, j] == k)
                if not len(ids): ids = np.arange(S)
                w = weights[ids]/weights[ids].sum(); price = float(w@prices[ids, j]); self.price[j, k] = price
                cur[k] = w@np.array([inf_convolution(self.grid, nxt[k], net[s, j]-q[j], price) for s in ids])
            v = cur
        self.initial_values = v

    def action(self, j, E, net, q, state=None):
        if self.legacy is not None:
            return self.legacy.action(j, E, net, q)
        k = int(np.sum(net > self.cuts[j]))
        return minimize_action(self.grid, self.future[j, k], E, net-q, self.price[j, k])


def terminal_values(grid, price, terminal, cuts):
    if terminal is not None:
        return 1000*np.abs(grid-terminal)
    if cuts:
        return np.maximum(0, np.max([a+b*grid for a, b in cuts], axis=0))
    return -price*grid


def minimize_action(grid, future, E, net_minus_q, price):
    lo = max(EMIN, E-M/ETA); hi = min(EMAX, E+ETA*M); a = net_minus_q
    candidates = np.unique(np.r_[grid[(grid >= lo) & (grid <= hi)], lo, hi, np.clip([E, E-a/ETA, E-a*ETA], lo, hi)])
    delta = candidates-E
    values = 5*price*np.maximum(0, a+np.maximum(ETA*delta, delta/ETA))+np.interp(candidates, grid, future)
    return float(candidates[np.argmin(values)])


def nonnegative_kernel(points, query, scales, prior):
    distances = cdist(np.atleast_2d(query)/scales, points/scales)**2
    # Unit bandwidth in legal historical standard deviations, fixed before development.
    logits = -.5*distances+np.log(np.maximum(prior, 1e-300))[None]
    w = np.exp(logits-logits.max(1, keepdims=True)); w /= w.sum(1, keepdims=True)
    return w


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
            v = np.array([inf_convolution(self.grid, future[s], net[s, j]-q[j], mean_price[s]) for s in range(S)])
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
