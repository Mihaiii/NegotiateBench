import math
from typing import List, Optional

class Agent:
    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.n_types = len(counts)
        
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turns_passed = 0
        
        # Initialize opponent estimates with deterministic variation
        total_items = sum(counts)
        if total_items > 0:
            base = self.total_value / total_items
            # Use type index to create variation (deterministic)
            self.opp_est = [base * (0.8 + 0.4 * (i * 3 % 7) / 7) for i in range(self.n_types)]
            
            # Normalize to match total value
            total = sum(self.opp_est[i] * counts[i] for i in range(self.n_types))
            if total > 0:
                scale = self.total_value / total
                self.opp_est = [v * scale for v in self.opp_est]
        else:
            self.opp_est = [0.0] * self.n_types
    
    def _update_opp_estimate(self, o: List[int]) -> None:
        """Stable opponent value estimation using log-space updates"""
        if o is None:
            return
        
        for i in range(self.n_types):
            if self.counts[i] == 0:
                continue
            
            keep_frac = (self.counts[i] - o[i]) / self.counts[i]
            
            # Log-space EMA update for stability
            log_old = math.log(max(1e-6, self.opp_est[i]))
            # Target: higher keep fraction → higher estimated value
            log_target = log_old + 1.5 * (keep_frac - 0.5)
            
            alpha = 0.15  # Conservative learning rate
            self.opp_est[i] = math.exp((1 - alpha) * log_old + alpha * log_target)
        
        # Renormalize to maintain total value
        total = sum(self.opp_est[i] * self.counts[i] for i in range(self.n_types))
        if total > 0:
            scale = self.total_value / total
            self.opp_est = [v * scale for v in self.opp_est]
    
    def _our_value(self, alloc: List[int]) -> int:
        """Calculate value of allocation to us"""
        return sum(a * v for a, v in zip(alloc, self.values))
    
    def _greedy_alloc(self, opp_budget: float) -> (List[int], int):
        """Greedy allocation: maximize our value within opponent's budget"""
        if opp_budget <= 0:
            return [0] * self.n_types, 0
        
        # Can we take everything?
        total_opp_cost = sum(self.opp_est[i] * self.counts[i] for i in range(self.n_types))
        if opp_budget >= total_opp_cost - 1e-9:
            return self.counts.copy(), self.total_value
        
        alloc = [0] * self.n_types
        our_val = 0
        opp_cost = 0
        
        # Zero-cost items first (free value for us)
        for i in range(self.n_types):
            if self.opp_est[i] < 1e-9 and self.values[i] > 0:
                alloc[i] = self.counts[i]
                our_val += alloc[i] * self.values[i]
        
        # Sort remaining by ratio: our value / opponent cost
        items = []
        for i in range(self.n_types):
            if self.counts[i] > 0 and alloc[i] == 0 and self.opp_est[i] >= 1e-9:
                ratio = self.values[i] / (self.opp_est[i] + 1e-9)
                items.append((ratio, i, self.counts[i]))
        
        items.sort(reverse=True, key=lambda x: x[0])
        
        for ratio, i, cnt in items:
            if opp_cost >= opp_budget:
                break
            
            max_take = min(cnt, int((opp_budget - opp_cost + 1e-9) / self.opp_est[i]))
            if max_take > 0:
                alloc[i] = max_take
                our_val += max_take * self.values[i]
                opp_cost += max_take * self.opp_est[i]
        
        return alloc, our_val
    
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        self.turns_passed += 1
        total_turns = self.max_rounds * 2
        turns_left = total_turns - self.turns_passed
        
        # Update opponent model and get offer value
        offer_val = self._our_value(o) if o is not None else 0
        if o is not None:
            self._update_opp_estimate(o)
        
        # Deadline-aware acceptance threshold
        progress = self.turns_passed / total_turns
        
        if turns_left == 0:
            threshold = 0.0  # Accept anything
        elif turns_left <= 2:
            threshold = 0.22 * self.total_value
        else:
            threshold = (0.66 - 0.34 * progress) * self.total_value
        
        # Accept if offer is good enough
        if o is not None and offer_val >= threshold:
            return None
        
        # Determine opponent's value budget (what they're likely to accept)
        opp_budget = self.total_value * (0.60 - 0.28 * progress)
        
        # Our target: improve over current offer or meet threshold
        target = max(threshold, offer_val * 1.06) if o is not None else threshold
        
        # Near deadline: cap our greediness
        if turns_left <= 2:
            target = min(target, self.total_value * 0.62)
        
        # Find best allocation within budget
        alloc, val = self._greedy_alloc(opp_budget)
        
        # If we can't beat their offer by enough near deadline, accept
        if o is not None and turns_left <= 2 and val < offer_val * 1.08:
            return None
        
        return alloc