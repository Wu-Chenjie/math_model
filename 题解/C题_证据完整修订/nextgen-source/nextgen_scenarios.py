"""As-of conditional trajectory measures; no future realization in planning."""
from dataclasses import dataclass, asdict
import hashlib
import json
import numpy as np
from scipy.spatial.distance import cdist
from forecasting import forecast_as_of


@dataclass(frozen=True)
class Config:
    horizon_hours: int = 48
    window: int = 28
    scenarios: int = 7
    alpha: float = .2
    gain_bound: float = 10.
    grid: int = 321
    bins: int = 3
    scenario_method: str = 'legacy'
    upper: str = 'legacy'
    lower: str = 'M0'
    tail_scale: float = 1.
    tail: str = 'linear'
    horizon_mode: str = 'fixed'
    final: float | None = 6000.
    ridge: float = 1e-4
    innovation_count: int = 10
    fusion_weight: float = 1.
    official_correction: float = 0.

    def identity(self):
        return hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()[:16]


def weighted_quantile(values, quantiles, weights):
    values = np.asarray(values); weights = np.asarray(weights)
    if np.allclose(weights, weights[0], rtol=0, atol=1e-15):
        return np.quantile(values, quantiles)
    order = np.argsort(values, kind='stable'); w = weights[order] / weights.sum()
    return np.interp(quantiles, np.cumsum(w)-.5*w, values[order])


def reduce_measure(distance, mass, count, max_swaps=20):
    """Deterministic weighted forward selection plus PAM swaps, not global PAM."""
    n = len(mass); count = min(count, n)
    selected = [int(np.argmin(distance @ mass))]
    closest = distance[:, selected[0]].copy()
    while len(selected) < count:
        improvement = mass @ (closest[:, None] - np.minimum(closest[:, None], distance))
        improvement[selected] = -np.inf
        chosen = int(np.argmax(improvement))
        if improvement[chosen] <= 1e-12:
            break  # Duplicate trajectories do not create independent representatives.
        selected.append(chosen); closest = np.minimum(closest, distance[:, chosen])
    swaps = 0
    for _ in range(max_swaps):
        old = float(mass @ np.min(distance[:, selected], axis=1)); best = old; choice = None
        for position in range(len(selected)):
            for replacement in range(n):
                if replacement in selected:
                    continue
                candidate = selected.copy(); candidate[position] = replacement
                cost = float(mass @ np.min(distance[:, candidate], axis=1))
                if cost < best - 1e-10:
                    best, choice = cost, candidate
        if choice is None:
            break
        selected = choice; swaps += 1
    selected = np.array(sorted(selected), dtype=int)
    assignments = np.argmin(distance[:, selected], axis=1)
    reduced = np.bincount(assignments, weights=mass, minlength=len(selected))
    positive = reduced > 0
    selected, reduced = selected[positive], reduced[positive]
    reduced /= reduced.sum()
    transport = float(mass @ np.min(distance[:, selected], axis=1))
    return selected, reduced, {'transport_distance': transport, 'pam_swaps': swaps}


def state_paths(net_error, price_error, seeds, alpha, variable):
    """Battery-node state: current n error, its EMA, lagged p error/EMA."""
    S, T = net_error.shape
    seeds = np.broadcast_to(seeds, (S, 4))
    x = np.empty((S, T, 4 if variable else 2))
    zn = seeds[:, 1].copy(); zp = seeds[:, 3].copy(); ep = seeds[:, 2].copy()
    for j in range(T):
        zn = (1-alpha)*zn + alpha*net_error[:, j]
        x[:, j, :2] = np.c_[net_error[:, j], zn]
        if variable:
            x[:, j, 2:] = np.c_[ep, zp]
            ep = price_error[:, j]
            zp = (1-alpha)*zp + alpha*ep
    return x


class ScenarioFactory:
    def __init__(self, data, selection, official, variable, alpha=.2,
                 fusion_weight=1., official_correction=0.):
        self.data, self.selection = data, selection
        self.official, self.variable, self.alpha = official, variable, alpha
        self.fusion_weight, self.official_correction = fusion_weight, official_correction
        self.forecasts = {}; self.blocks = {}
        n = (data['load']-data['pv']).ravel()/6; p = data['price'].ravel()
        self.ledger = np.full((len(n), 4), np.nan)
        en = n[144:]-n[:-144]; ep = p[144:]-p[:-144]
        zn, zp = en[0], ep[0]
        for j in range(len(en)):
            zn = (1-alpha)*zn+alpha*en[j]; zp = (1-alpha)*zp+alpha*ep[j]
            self.ledger[j+144] = en[j], zn, ep[j], zp

    def seed(self, asof):
        assert asof > 144
        seed = self.ledger[asof-1].copy()
        assert np.isfinite(seed).all()
        return seed

    def forecast(self, origin, length):
        key = origin, length
        if key not in self.forecasts:
            visible = dict(self.data)
            for name in ('load', 'pv', 'price'):
                visible[name] = self.data[name].copy()
                visible[name].ravel()[origin:] = np.nan
            visible['forecast'] = self.data['forecast'].copy()
            visible['forecast'].reshape(-1, 24)[origin//36+1:] = np.nan
            pred = forecast_as_of(visible, self.selection, origin,
                                  np.arange(origin, origin+length), self.official, self.variable)
            if self.official and (self.fusion_weight != 1. or self.official_correction != 0.):
                targets = np.arange(origin, origin+length)
                historical = forecast_as_of(visible, self.selection, origin, targets, False, self.variable)
                covered = targets+1 <= origin//36*36+144
                adjustment = 0.
                if self.official_correction:
                    errors = []
                    for past_issue in range(max(144, origin-36)//36*36, origin, 36):
                        observed = np.arange(max(origin-36, past_issue), min(origin, past_issue+36))
                        if not len(observed): continue
                        old = forecast_as_of(visible, self.selection, past_issue, observed, True, self.variable)
                        errors.extend((visible['pv'].ravel()[observed]-old['pv']).tolist())
                    adjustment = self.official_correction*float(np.mean(errors)) if errors else 0.
                official_pv = np.maximum(0, pred['pv']+adjustment*np.exp(-(targets-origin)/36.))
                pred['pv'][covered] = self.fusion_weight*official_pv[covered]+(1-self.fusion_weight)*historical['pv'][covered]
                pred['net'] = (pred['load']-pred['pv'])/6
            assert np.isfinite(pred['net']).all() and np.isfinite(pred['price']).all()
            self.forecasts[key] = pred
        return self.forecasts[key]

    def block(self, origin, length, asof):
        assert origin+length <= asof, 'Unripe historical residual block'
        key = origin, length
        if key not in self.blocks:
            past = self.forecast(origin, length); targets = slice(origin, origin+length)
            en = (self.data['load'].ravel()[targets]-self.data['pv'].ravel()[targets])/6-past['net']
            ep = self.data['price'].ravel()[targets]-past['price']
            self.blocks[key] = en, ep
        return self.blocks[key]

    def build(self, asof, end, config):
        assert config.alpha == self.alpha, 'Factory and policy EMA parameters differ'
        assert config.fusion_weight == self.fusion_weight and config.official_correction == self.official_correction
        T = end-asof; day, phase = divmod(asof, 144)
        origins = np.array([h*144+phase for h in range(7, day)
                            if h*144+phase+T <= asof][-config.window:], dtype=int)
        if not len(origins):
            raise ValueError('No mature historical blocks')
        pairs = [self.block(int(h), T, asof) for h in origins]
        rn, rp = np.array([v[0] for v in pairs]), np.array([v[1] for v in pairs])
        seeds = np.array([self.seed(int(h)) for h in origins]); seed = self.seed(asof)
        dimension = 4 if self.variable else 2
        scales = np.maximum(np.std(seeds[:, :dimension], axis=0, ddof=1 if len(seeds)>1 else 0), 1e-8)
        standardized = seeds[:, :dimension]/scales
        origin_distance = np.linalg.norm((seeds[:, :dimension]-seed[:dimension])/scales, axis=1)
        pair_distance = cdist(standardized, standardized)
        nonzero = pair_distance[pair_distance > 1e-10]
        bandwidth = float(np.median(nonzero)) if len(nonzero) else 1.
        if config.scenario_method == 'conditional':
            logweights = -.5*(origin_distance/bandwidth)**2
            mass = np.exp(logweights-logweights.max()); mass /= mass.sum()
        else:
            mass = np.full(len(origins), 1/len(origins))
        ns = max(float(np.std(rn)), 1e-8); ps = max(float(np.std(rp)), 1e-8)
        joint = np.c_[rn/ns, rp/ps] if self.variable else rn/ns
        distances = cdist(joint, joint)/np.sqrt(joint.shape[1])
        if config.scenario_method == 'legacy':
            selected = np.arange(len(origins))
            if len(selected) > config.scenarios:
                selected = np.linspace(0, len(selected)-1, config.scenarios).round().astype(int)
            weights = np.full(len(selected), 1/len(selected))
            reduction = {'transport_distance': float(mass @ distances[:, selected].min(1)), 'pam_swaps': 0}
        elif config.scenario_method in ('medoids', 'conditional'):
            selected, weights, reduction = reduce_measure(distances, mass, config.scenarios)
        else:
            raise ValueError(config.scenario_method)
        current = self.forecast(asof, T)
        completion_length = (-end) % 144
        completion = np.maximum(0, self.forecast(asof, T+completion_length)['net'][T:]) if completion_length else np.array([])
        net = current['net'][None, :]+rn[selected]
        prices = np.maximum(.001, current['price'][None, :]+rp[selected]) if self.variable else np.tile(current['price'], (len(selected), 1))
        if config.scenario_method == 'legacy':
            # Preserve even the floating-point evaluation order of the accepted
            # generator for the single-factor horizon compatibility experiments.
            net = np.array([current['net']+(self.data['load'].ravel()[h:h+T]-self.data['pv'].ravel()[h:h+T])/6-self.forecast(int(h), T)['net'] for h in origins[selected]])
            if self.variable:
                prices = np.array([np.maximum(.001, current['price']+self.data['price'].ravel()[h:h+T]-self.forecast(int(h), T)['price']) for h in origins[selected]])
        xn = net-current['net']; xp = prices-current['price']
        states = state_paths(xn, xp, seed, config.alpha, self.variable)
        history_states = state_paths(rn, rp, seeds, config.alpha, self.variable)
        tails = rn.sum(1); threshold = weighted_quantile(tails, [.95], mass)[0]
        metadata = {
            'as_of': asof, 'end': end, 'horizon_slots': T,
            'history_origins': origins.tolist(), 'history_days': (origins//144).tolist(),
            'latest_training_target_exclusive': int(origins.max()+T),
            'maturity_end': int(origins.max()+T), 'requested_window': config.window,
            'effective_window': len(origins), 'requested_scenarios': config.scenarios,
            'effective_scenarios': len(selected), 'representative_origins': origins[selected].tolist(),
            'candidate_weights': mass.tolist(), 'scenario_weights': weights.tolist(),
            'weight_ess': float(1/(mass@mass)), 'bandwidth': bandwidth,
            'state_seed': seed.tolist(), 'state_seed_observation_cutoff': asof-1,
            'seed_reference': 'previous-day same-slot forecast, EMA initialized at first valid error',
            'state_reference': 'fixed current forecast origin; deterministic restart at next planning origin',
            'scenario_method': config.scenario_method, 'tail95_representative_retained': bool(np.any(tails[selected] >= threshold)),
            'max_net_residual_retained': bool(np.argmax(rn.max(1)) in selected),
            'max_price_residual_retained': bool(np.argmax(rp.max(1)) in selected) if self.variable else None,
            'official_covered_slots': current['official_covered_slots'], **reduction}
        metadata['outside_core_original_contract_completion'] = {
            'start': end, 'end': end+completion_length, 'forecast_information_cutoff': asof,
            'scheduled_release': end//144*144 if completion_length else None,
            'q_kwh': completion.tolist(), 'feedback_gain': 0.,
            'rule': 'common nonnegative current-origin forecast; suffix is a causal extension, not optimized delivery',
            'delivery_cost_in_core_objective': False}
        return {'net': net, 'prices': prices, 'weights': weights, 'states': states,
                'history_states': history_states, 'history_net_error': rn,
                'history_price_error': rp, 'history_seeds': seeds, 'mass': mass,
                'forecast': current, 'seed': seed, 'origins': origins, 'meta': metadata}
