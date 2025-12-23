import math

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts[:]
        self.values = values[:]
        self.n_types = len(counts)
        self.total = sum(c * v for c, v in zip(counts, values))
        self.max_rounds = max_rounds
        self.me = me
        self.n_calls = 0
        total_items = sum(counts)
        avg = self.total / total_items if total_items > 0 else 0.0
        self.est_opp = [avg] * self.n_types
        self.opp_offers = []

    def opp_val_of_alloc(self, alloc: list[int]) -> float:
        return sum(self.est_opp[i] * alloc[i] for i in range(self.n_types))

    def update_est_opp(self, o: list[int]):
        self.opp_offers.append(o)
        num_offers = len(self.opp_offers)
        avg_keep = [0.0] * self.n_types
        for i in range(self.n_types):
            sum_keep = sum(1.0 - oo[i] / self.counts[i] if self.counts[i] > 0 else 1.0 for oo in self.opp_offers)
            avg_keep[i] = sum_keep / num_offers
        sum_weight = sum(avg_keep[j] * self.counts[j] for j in range(self.n_types))
        if sum_weight > 0:
            scale = float(self.total) / sum_weight
            self.est_opp = [avg_keep[j] * scale for j in range(self.n_types)]

    def get_greedy_prop(self, target: float) -> list[int]:
        if target <= 0:
            return [0] * self.n_types
        type_order = sorted(range(self.n_types), key=lambda x: self.values[x] / max(self.est_opp[x], 1e-6), reverse=True)
        prop = [0] * self.n_types
        rem = target
        for t in type_order:
            if rem <= 0:
                break
            v = self.values[t]
            if v <= 0:
                continue
            max_take = self.counts[t]
            needed = math.ceil(rem / v)
            take = min(max_take, needed)
            prop[t] = take
            rem -= take * v
        return prop

    def _should_accept(self, myval: float, call_num: int) -> bool:
        if self.max_rounds <= 1:
            return myval >= 0.01 * self.total
        progress = min(1.0, (call_num - 1.0) / max(self.max_rounds - 1.0, 1.0))
        thresh_frac = 0.5 - 0.48 * progress
        return myval >= thresh_frac * self.total

    def _generate_proposal(self, call_num: int) -> list[int]:
        if self.max_rounds <= 1:
            return self.get_greedy_prop(0.5 * self.total)
        progress = min(1.0, (call_num - 1.0) / max(self.max_rounds - 1.0, 1.0))
        opp_thresh_frac = 0.5 - 0.3 * progress
        opp_threshold = opp_thresh_frac * self.total
        fracs = [1.0 - 0.05 * i for i in range(21)]
        candidates = []
        for f in fracs:
            prop = self.get_greedy_prop(f * self.total)
            myv = sum(self.values[i] * prop[i] for i in range(self.n_types))
            rest = [self.counts[i] - prop[i] for i in range(self.n_types)]
            oppv_est = self.opp_val_of_alloc(rest)
            candidates.append((myv, oppv_est, prop))
        candidates.sort(key=lambda x: -x[0])
        for myv, oppv, prop in candidates:
            if oppv >= opp_threshold:
                return prop
        return candidates[0][2]

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.n_calls += 1
        if o is not None:
            self.update_est_opp(o)
            my_val_accept = sum(self.values[i] * o[i] for i in range(self.n_types))
            if self._should_accept(my_val_accept, self.n_calls):
                return None
        prop = self._generate_proposal(self.n_calls)
        return prop