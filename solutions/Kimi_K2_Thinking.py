from typing import List, Optional

class Agent:
    """
    Haggling negotiation agent that maximizes value through adaptive opponent modeling
    and strategic concessions. Uses opponent's offer history to estimate their valuations
    and adjusts reservation utility dynamically based on remaining rounds.
    """

    def __init__(self, me: int, counts: List[int], values: List[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        
        # Core calculations
        self.num_types = len(counts)
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.total_items = sum(counts)
        
        # Round tracking (increments each time it's our turn)
        self.current_round = 0
        
        # Opponent modeling
        self.opponent_offers_received = 0
        self.opponent_keep_sum = [0] * self.num_types
        
        # Initialize opponent valuations with uniform prior
        self.opponent_valuations = self._initialize_opponent_valuations()
        
        # Track best offer seen
        self.best_offer_value = -1
        
        # Track last opponent offer for concession detection
        self.last_opponent_offer = None
    
    def _initialize_opponent_valuations(self) -> List[float]:
        """Initialize opponent valuations using uniform prior scaled to total value"""
        if self.total_items == 0:
            return [0.0] * self.num_types
        
        uniform_val = self.total_value / self.total_items
        valuations = [uniform_val] * self.num_types
        
        # Normalize to ensure sum matches total_value
        total_est = sum(v * c for v, c in zip(valuations, self.counts))
        if total_est > 0:
            scale = self.total_value / total_est
            valuations = [v * scale for v in valuations]
        
        return valuations
    
    def _our_value(self, allocation: List[int]) -> int:
        """Calculate our value for an allocation"""
        return sum(v * a for v, a in zip(self.values, allocation))
    
    def _opponent_value(self, allocation: List[int]) -> float:
        """Calculate opponent's estimated value (they get the complement)"""
        opp_gets = [c - a for c, a in zip(self.counts, allocation)]
        return sum(ov * o for ov, o in zip(self.opponent_valuations, opp_gets))
    
    def _update_opponent_model(self, offer: List[int]) -> None:
        """Update opponent valuation estimates based on their offer"""
        self.opponent_offers_received += 1
        
        # Detect concessions and adjust valuations
        if self.last_opponent_offer is not None:
            for i in range(self.num_types):
                if offer[i] > self.last_opponent_offer[i]:
                    # Opponent offered us more of this type - they likely value it less
                    self.opponent_valuations[i] *= 0.95
        
        self.last_opponent_offer = offer[:]
        
        # Track what opponent keeps for themselves
        for i in range(self.num_types):
            keep = self.counts[i] - offer[i]
            self.opponent_keep_sum[i] += keep
        
        # Re-estimate valuations based on average keep proportion
        if self.opponent_offers_received > 0:
            estimates = []
            for i in range(self.num_types):
                if self.counts[i] == 0:
                    estimates.append(0.0)
                else:
                    prop = self.opponent_keep_sum[i] / (self.opponent_offers_received * self.counts[i])
                    # Bound proportions to avoid extremes
                    prop = max(0.05, min(0.95, prop))
                    estimates.append(prop)
            
            # Scale to match total value constraint
            total_est = sum(e * c for e, c in zip(estimates, self.counts))
            if total_est > 0:
                scale = self.total_value / total_est
                self.opponent_valuations = [e * scale for e in estimates]
    
    def _reservation_value(self) -> float:
        """Dynamic reservation utility that decreases as deadline approaches"""
        if self.total_value == 0:
            return 0
        
        rounds_left = self.max_rounds - self.current_round + 1
        
        # Last round: accept anything above 10% of total value
        if rounds_left <= 1:
            return self.total_value * 0.10
        
        # Linear decrease from 85% to 20%
        fraction = (rounds_left - 1) / max(1, self.max_rounds - 1)
        return self.total_value * (0.20 + 0.65 * fraction)
    
    def _target_opponent_value(self) -> float:
        """Target opponent utility that increases as deadline approaches"""
        if self.total_value == 0:
            return 0
        
        rounds_left = self.max_rounds - self.current_round + 1
        
        # Linear increase from 25% to 70%
        elapsed = (self.max_rounds - rounds_left) / max(1, self.max_rounds - 1)
        return self.total_value * (0.25 + 0.45 * elapsed)
    
    def _should_accept(self, offer: List[int]) -> bool:
        """Determine if we should accept the opponent's offer"""
        our_val = self._our_value(offer)
        
        # Track best offer
        if our_val > self.best_offer_value:
            self.best_offer_value = our_val
        
        # Accept if meets reservation threshold
        if our_val >= self._reservation_value():
            return True
        
        # Last chance: accept any positive value
        rounds_left = self.max_rounds - self.current_round
        if rounds_left <= 0 and our_val > 0:
            return True
        
        return False
    
    def _make_offer(self) -> List[int]:
        """Generate a concession-aware counter-offer"""
        # Degenerate case: everything worthless to us
        if self.total_value == 0:
            return [0] * self.num_types
        
        # Target opponent utility
        target_opp = self._target_opponent_value()
        
        # Start by keeping everything
        allocation = self.counts[:]
        current_opp_val = self._opponent_value(allocation)
        
        # Already meeting target
        if current_opp_val >= target_opp:
            return allocation
        
        # Build list of individual items we can concede
        items = []
        for i in range(self.num_types):
            # Only consider items we value less than opponent (or equal)
            if self.opponent_valuations[i] >= self.values[i] * 0.8:
                for _ in range(self.counts[i]):
                    ratio = (self.opponent_valuations[i] / max(1, self.values[i]))
                    items.append({
                        'type': i,
                        'our_val': self.values[i],
                        'opp_val': self.opponent_valuations[i],
                        'ratio': ratio
                    })
        
        # Sort by concession value (opp/our ratio), highest first
        items.sort(key=lambda x: x['ratio'], reverse=True)
        
        # Concede items until target reached or no more concessions
        for item in items:
            if current_opp_val >= target_opp:
                break
            
            type_idx = item['type']
            if allocation[type_idx] > 0:
                allocation[type_idx] -= 1
                current_opp_val += item['opp_val']
        
        return allocation
    
    def offer(self, o: Optional[List[int]]) -> Optional[List[int]]:
        """
        Main negotiation entry point.
        Called each round with opponent's offer (None if we're first in round 1).
        Returns our counter-offer or None to accept.
        """
        self.current_round += 1
        
        if o is not None:
            self._update_opponent_model(o)
            
            if self._should_accept(o):
                return None
        
        return self._make_offer()