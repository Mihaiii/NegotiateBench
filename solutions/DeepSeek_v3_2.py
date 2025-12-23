import math
from typing import List, Optional

class Agent:
    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.round = 0
        self.n = len(counts)
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Opponent value estimate: start with our values (same total)
        self.opp_values = values[:]
        self.opponent_offers = []
        
        # Candidate allocations
        self.candidates = self.generate_candidates()
        self.candidate_my_values = [self.value_of(a, self.values) for a in self.candidates]
        self.candidate_opp_values = [self.value_of(self.complement(a), self.opp_values) for a in self.candidates]
        
        # Strategy parameters
        self.start_target_ratio = 0.9
        self.min_target_ratio = 0.5
        self.concession_exp = 1.5
        self.required_opp_factor = 1.0
        self.required_opp_decay = 0.95
        
    def generate_candidates(self) -> List[List[int]]:
        """Generate a diverse set of allocations."""
        total_alloc = 1
        for c in self.counts:
            total_alloc *= (c + 1)
        if total_alloc <= 100000:
            return self.enumerate_all()
        else:
            return self.heuristic_all()
    
    def enumerate_all(self) -> List[List[int]]:
        """Enumerate all possible allocations (feasible for small problems)."""
        allocs = []
        def dfs(idx: int, cur: List[int]):
            if idx == self.n:
                allocs.append(cur[:])
                return
            for k in range(self.counts[idx] + 1):
                cur.append(k)
                dfs(idx + 1, cur)
                cur.pop()
        dfs(0, [])
        return allocs
    
    def heuristic_all(self) -> List[List[int]]:
        """Generate allocations using greedy and targeted strategies."""
        allocs = []
        # Extremes
        allocs.append(self.counts[:])
        allocs.append([0] * self.n)
        # Greedy for various target ratios
        for ratio in [0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]:
            alloc = self.greedy_for_ratio(ratio)
            if alloc not in allocs:
                allocs.append(alloc)
        # Give away zero‑value items
        zero_alloc = [0] * self.n
        for i in range(self.n):
            if self.values[i] > 0:
                zero_alloc[i] = self.counts[i]
        if zero_alloc not in allocs:
            allocs.append(zero_alloc)
        # Take only high‑value items
        high_alloc = [0] * self.n
        items = sorted(range(self.n), key=lambda i: self.values[i], reverse=True)
        for i in items:
            if self.values[i] > 0:
                high_alloc[i] = self.counts[i]
        if high_alloc not in allocs:
            allocs.append(high_alloc)
        return allocs
    
    def greedy_for_ratio(self, ratio: float) -> List[int]:
        """Greedy allocation aiming for a fraction of total value."""
        target = self.total_value * ratio
        alloc = [0] * self.n
        cur = 0
        items = sorted(range(self.n), key=lambda i: self.values[i], reverse=True)
        for i in items:
            if self.values[i] <= 0:
                continue
            max_take = self.counts[i]
            if cur + self.values[i] * max_take <= target:
                alloc[i] = max_take
                cur += self.values[i] * max_take
            else:
                needed = min(max_take, int((target - cur) / self.values[i]))
                if needed > 0:
                    alloc[i] = needed
                    cur += needed * self.values[i]
        # If under, add more
        if cur < target:
            for i in items:
                remaining = self.counts[i] - alloc[i]
                if remaining > 0 and self.values[i] > 0:
                    add = min(remaining, int((target - cur) / self.values[i]) + 1)
                    if add > 0:
                        alloc[i] += add
                        cur += add * self.values[i]
                        if cur >= target:
                            break
        return alloc
    
    def value_of(self, alloc: List[int], values: List[int]) -> int:
        return sum(alloc[i] * values[i] for i in range(self.n))
    
    def complement(self, alloc: List[int]) -> List[int]:
        return [self.counts[i] - alloc[i] for i in range(self.n)]
    
    def update_opponent_values(self, offer: List[int]):
        """Update opponent value estimates based on their offer."""
        kept = [self.counts[i] - offer[i] for i in range(self.n)]
        alpha = 0.3
        new_opp = [0.0] * self.n
        for i in range(self.n):
            if self.counts[i] > 0:
                kept_ratio = kept[i] / self.counts[i]
                adj = 1.0 + alpha * (kept_ratio - 0.5)
                new_opp[i] = self.opp_values[i] * adj
            else:
                new_opp[i] = self.opp_values[i]
        # Preserve total value
        new_total = sum(self.counts[i] * new_opp[i] for i in range(self.n))
        if new_total > 0:
            scale = self.total_value / new_total
            new_opp = [v * scale for v in new_opp]
        self.opp_values = new_opp
        # Update cached values
        self.candidate_opp_values = [self.value_of(self.complement(a), self.opp_values) for a in self.candidates]
    
    def get_current_target(self) -> float:
        """Compute target value for us based on remaining rounds."""
        rounds_left = self.max_rounds - self.round
        if rounds_left <= 0:
            return self.total_value * self.min_target_ratio
        t = (rounds_left / self.max_rounds) ** self.concession_exp
        r = self.min_target_ratio + (self.start_target_ratio - self.min_target_ratio) * t
        return self.total_value * r
    
    def get_required_opponent_value(self) -> float:
        """Estimate the minimum value the opponent expects for themselves."""
        if not self.opponent_offers:
            return 0.0
        opp_self_vals = []
        for offer in self.opponent_offers:
            kept = self.complement(offer)
            val = self.value_of(kept, self.opp_values)
            opp_self_vals.append(val)
        max_self = max(opp_self_vals)
        factor = self.required_opp_factor * (self.required_opp_decay ** (self.round - 1))
        required = max_self * factor
        return min(required, self.total_value * 0.9)
    
    def find_best_counteroffer(self, target: float, required_opp: float) -> List[int]:
        """Select the best allocation meeting target and opponent requirements."""
        best_alloc = None
        best_val = -1
        # First try to satisfy both
        for i, alloc in enumerate(self.candidates):
            my_val = self.candidate_my_values[i]
            opp_val = self.candidate_opp_values[i]
            if my_val >= target and opp_val >= required_opp:
                if my_val > best_val:
                    best_val = my_val
                    best_alloc = alloc
        if best_alloc is not None:
            return best_alloc
        # Relax target
        for i, alloc in enumerate(self.candidates):
            my_val = self.candidate_my_values[i]
            opp_val = self.candidate_opp_values[i]
            if opp_val >= required_opp:
                if my_val > best_val:
                    best_val = my_val
                    best_alloc = alloc
        if best_alloc is not None:
            return best_alloc
        # Fallback: maximize our value
        best_alloc = max(zip(self.candidates, self.candidate_my_values), key=lambda x: x[1])[0]
        return best_alloc
    
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.round += 1
        
        if o is not None:
            self.opponent_offers.append(o)
            self.update_opponent_values(o)
            offer_val = self.value_of(o, self.values)
            
            # Decide whether to accept
            target = self.get_current_target()
            rounds_left = self.max_rounds - self.round
            if rounds_left == 0:
                if offer_val >= self.total_value * self.min_target_ratio:
                    return None
            else:
                if offer_val >= target:
                    # Check if we can do significantly better
                    req_opp = self.get_required_opponent_value()
                    best_counter = self.find_best_counteroffer(target, req_opp)
                    best_val = self.value_of(best_counter, self.values)
                    if best_val <= offer_val * 1.1:
                        return None
                    if rounds_left <= 2 and offer_val >= self.total_value * 0.6:
                        return None
        
        # Make a counteroffer
        target = self.get_current_target()
        req_opp = self.get_required_opponent_value()
        return self.find_best_counteroffer(target, req_opp)