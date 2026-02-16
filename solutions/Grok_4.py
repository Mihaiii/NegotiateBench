import math

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.n_types = len(counts)
        self.total = sum(counts[i] * values[i] for i in range(self.n_types))
        self.max_turns = 2 * max_rounds
        self.my_turn_number = 0
        self.partner_offers = []
        self.has_advantage = (self.max_turns % 2 == 0 and self.me == 0) or (self.max_turns % 2 == 1 and self.me == 1)

    def value(self, o: list[int]) -> float:
        return sum(o[i] * self.values[i] for i in range(self.n_types))

    def estimate_v_partner(self) -> list[float]:
        if not self.partner_offers:
            total_items = sum(self.counts)
            if total_items == 0:
                return [0.0] * self.n_types
            unit = self.total / total_items
            return [unit] * self.n_types
        num_off = len(self.partner_offers)
        avg_taken = [0.0] * self.n_types
        sum_weights = 0.0
        alpha = 0.5
        for k in range(num_off):
            weight = alpha ** (num_off - 1 - k)
            o = self.partner_offers[k]
            for i in range(self.n_types):
                avg_taken[i] += weight * (self.counts[i] - o[i])
            sum_weights += weight
        for i in range(self.n_types):
            avg_taken[i] /= sum_weights
        sum_avg = sum(avg_taken)
        if sum_avg == 0:
            return [0.0] * self.n_types
        c = self.total / sum_avg
        v = [0.0] * self.n_types
        for i in range(self.n_types):
            v[i] = c * (avg_taken[i] / self.counts[i]) if self.counts[i] > 0 else 0.0
        return v

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.my_turn_number += 1
        if self.me == 0:
            current_turn = 2 * (self.my_turn_number - 1) + 1
        else:
            current_turn = 2 * self.my_turn_number
        remaining = self.max_turns - current_turn
        if o is not None:
            self.partner_offers.append(o)
        is_last_turn = remaining == 0
        is_penultimate = current_turn == self.max_turns - 1
        progress = current_turn / self.max_turns if self.max_turns > 0 else 1.0
        v_partner = self.estimate_v_partner()
        power = 5 if self.has_advantage else 1
        g = progress ** power
        if is_last_turn:
            min_accept = 0
            partner_threshold = 0
        elif is_penultimate:
            min_accept = self.total * 0.9
            partner_threshold = 0
        else:
            if self.has_advantage:
                my_share_frac = 0.75 + 0.25 * g
            else:
                my_share_frac = 0.7 - 0.3 * g
            min_accept = self.total * my_share_frac
            partner_threshold = self.total * (1 - my_share_frac)
        if o is not None:
            my_val = self.value(o)
            if my_val >= min_accept:
                return None
        m = [0] * self.n_types
        current_util = 0.0
        for i in range(self.n_types):
            if self.values[i] == 0:
                m[i] = self.counts[i]
                current_util += m[i] * v_partner[i]
        if not is_last_turn:
            target = partner_threshold
            if is_penultimate:
                target = 0.01
            remaining_needed = target - current_util
            if remaining_needed > 0:
                candidates = [i for i in range(self.n_types) if v_partner[i] > 0 and self.values[i] > 0 and self.counts[i] - m[i] > 0]
                if candidates:
                    if is_penultimate or remaining_needed < 1.0:
                        min_unit_v = self.total / 5.0
                        safe_candidates = [i for i in candidates if v_partner[i] >= min_unit_v]
                        if safe_candidates:
                            safe_candidates.sort(key=lambda i: (self.values[i], -v_partner[i]))
                            best = safe_candidates[0]
                        else:
                            candidates.sort(key=lambda i: (-v_partner[i], self.values[i]))
                            best = candidates[0]
                        num = 1
                        m[best] += num
                        current_util += num * v_partner[best]
                    else:
                        candidates.sort(key=lambda i: (-v_partner[i] / self.values[i] if self.values[i] > 0 else 0, self.values[i]))
                        for i in candidates:
                            util_per = v_partner[i]
                            max_give = self.counts[i] - m[i]
                            num_needed = math.ceil(remaining_needed / util_per)
                            num = min(num_needed, max_give)
                            m[i] += num
                            added = num * util_per
                            current_util += added
                            remaining_needed -= added
                            if remaining_needed <= 0:
                                break
            elif remaining_needed < 0:
                excess = -remaining_needed
                while excess > 0:
                    candidates = [i for i in range(self.n_types) if self.values[i] == 0 and m[i] > 0 and v_partner[i] > 0 and v_partner[i] <= excess]
                    if not candidates:
                        break
                    best = max(candidates, key=lambda i: v_partner[i])
                    m[best] -= 1
                    current_util -= v_partner[best]
                    excess -= v_partner[best]
            # Add minimal if necessary
            if current_util <= 0 and (partner_threshold > 0 or is_penultimate) and not is_last_turn:
                candidates = [i for i in range(self.n_types) if v_partner[i] > 0 and self.values[i] > 0 and self.counts[i] - m[i] > 0]
                if candidates:
                    candidates.sort(key=lambda i: (v_partner[i], self.values[i]))
                    best = candidates[0]
                    m[best] += 1
                    current_util += v_partner[best]
        my_offer = [self.counts[i] - m[i] for i in range(self.n_types)]
        return my_offer