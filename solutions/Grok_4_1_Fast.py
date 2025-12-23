import math

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts[:]
        self.values = values[:]
        self.n_types = len(counts)
        self.total = sum(c * v for c, v in zip(counts, values)) * 1.0
        self.max_rounds = max_rounds
        self.n_calls = 0
        total_items = sum(counts)
        avg_item = self.total / total_items if total_items > 0 else 0.0
        self.est_opp = [avg_item] * self.n_types
        self.opp_offers = []

    def opp_val_of_alloc(self, alloc: list[int]) -> float:
        return sum(self.est_opp[i] * alloc[i] for i in range(self.n_types))

    def update_est_opp(self, o: list[int]):
        self.opp_offers.append(o)
        if len(self.opp_offers) > 10:
            self.opp_offers = self.opp_offers[-10:]
        num_offers = len(self.opp_offers)
        avg_keep = [0.0] * self.n_types
        for i in range(self.n_types):
            if self.counts[i] == 0:
                avg_keep[i] = 1.0
                continue
            sum_keep_frac = sum((self.counts[i] - oo[i]) * 1.0 / self.counts[i] for oo in self.opp_offers)
            avg_keep[i] = sum_keep_frac / num_offers
        sum_weight = sum(avg_keep[j] * self.counts[j] for j in range(self.n_types))
        if sum_weight > 1e-6:
            scale = self.total / sum_weight
            self.est_opp = [avg_keep[j] * scale for j in range(self.n_types)]

    def get_greedy_our(self, target: float) -> list[int]:
        if target <= 0:
            return [0] * self.n_types
        type_order = sorted(range(self.n_types), key=lambda x: self.values[x], reverse=True)
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

    def get_prop_for_opp_thresh(self, opp_thresh: float) -> list[int]:
        if opp_thresh >= self.total:
            return [0] * self.n_types
        budget = self.total - opp_thresh
        type_order = sorted(range(self.n_types), key=lambda x: self.values[x] / max(self.est_opp[x], 1e-6), reverse=True)
        prop = [0] * self.n_types
        rem_budget = budget
        for t in type_order:
            if rem_budget <= 0:
                break
            est = self.est_opp[t]
            if est <= 0:
                prop[t] = self.counts[t]
                continue
            max_take = self.counts[t]
            can_take = rem_budget / est
            take = min(max_take, math.floor(can_take))
            prop[t] = take
            rem_budget -= take * est
        return prop

    def _should_accept(self, myval: float, call_num: int) -> bool:
        if myval <= 0:
            return False
        if self.max_rounds <= 1:
            return myval >= 0.3 * self.total
        progress = min(1.0, (call_num - 1.0) / max(self.max_rounds - 1.0, 1.0))
        thresh_frac = 0.75 - 0.55 * progress
        if progress > 0.85:
            thresh_frac = 0.2 - 0.15 * (progress - 0.85) / 0.15
            thresh_frac = max(thresh_frac, 0.05)
        return myval >= thresh_frac * self.total

    def _generate_proposal(self, call_num: int) -> list[int]:
        if self.max_rounds <= 1:
            return self.get_prop_for_opp_thresh(0.5 * self.total)
        if len(self.opp_offers) == 0:
            return self.get_greedy_our(0.75 * self.total)
        progress = min(1.0, (call_num - 1.0) / max(self.max_rounds - 1.0, 1.0))
        opp_thresh_frac = 0.25 + 0.35 * progress
        opp_threshold = opp_thresh_frac * self.total
        return self.get_prop_for_opp_thresh(opp_threshold)

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.n_calls += 1
        if o is not None:
            self.update_est_opp(o)
            my_val_accept = sum(self.values[i] * o[i] for i in range(self.n_types))
            if self._should_accept(my_val_accept, self.n_calls):
                return None
        prop = self._generate_proposal(self.n_calls)
        return prop