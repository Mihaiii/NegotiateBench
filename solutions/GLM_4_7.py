import math

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.num_types = len(counts)
        self.max_rounds = max_rounds
        self.turn = 0
        
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Opponent value model - uniform prior
        self.opp_values = [1.0] * self.num_types
        
        # Track offers
        self.my_offers = []
        self.opp_offers = []
        self.best_opp_value = 0
        
        # Track value to ensure monotonic concessions
        self.last_offer_value = None
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        turns_left = self.max_rounds * 2 - self.turn
        round_num = (self.turn - 1) // 2
        
        # Process opponent's offer
        if o is not None:
            self.opp_offers.append(o)
            self._update_opp_model(o)
            
            my_val = sum(self.values[i] * o[i] for i in range(self.num_types))
            self.best_opp_value = max(self.best_opp_value, my_val)
            
            if self._should_accept(o, my_val, turns_left, round_num):
                return None
        
        # Generate counter-offer
        new_offer = self._make_offer(round_num)
        offer_val = sum(self.values[i] * new_offer[i] for i in range(self.num_types))
        
        # Ensure monotonic concession
        if self.last_offer_value is not None and offer_val > self.last_offer_value:
            new_offer = self.my_offers[-1] if self.my_offers else new_offer
        
        self.last_offer_value = sum(self.values[i] * new_offer[i] for i in range(self.num_types))
        self.my_offers.append(new_offer)
        return new_offer
    
    def _should_accept(self, offer: list[int], my_val: float, turns_left: int, round_num: int) -> bool:
        # Last turn: accept anything positive
        if turns_left == 0:
            return my_val > 0
        
        progress = round_num / self.max_rounds
        
        # Progressive acceptance threshold: 55% -> 10%
        min_val = self.total_value * (0.55 - 0.45 * progress)
        
        if my_val >= min_val:
            return True
        
        # Fairness check: accept if both parties get reasonable amounts
        opp_val = sum(self.opp_values[i] * (self.counts[i] - offer[i]) for i in range(self.num_types))
        if progress > 0.4 and my_val >= self.total_value * 0.4 and opp_val >= self.total_value * 0.4:
            return True
        
        return False
    
    def _update_opp_model(self, offer: list[int]):
        """Update opponent value estimates with stable learning."""
        for i in range(self.num_types):
            kept = self.counts[i] - offer[i]
            given = offer[i]
            
            # Small learning rate for stability
            if kept > given:
                self.opp_values[i] *= 1.05
            elif given > kept:
                self.opp_values[i] *= 0.95
        
        # Normalize to maintain total value
        total = sum(self.opp_values[i] * self.counts[i] for i in range(self.num_types))
        if total > 0:
            factor = self.total_value / total
            self.opp_values = [v * factor for v in self.opp_values]
    
    def _make_offer(self, round_num: int) -> list[int]:
        """Generate counter-offer with steady concessions."""
        
        # Calculate target value
        if self.my_offers:
            prev_val = self.last_offer_value if self.last_offer_value else sum(self.values[i] * self.my_offers[-1][i] for i in range(self.num_types))
            
            # Gradual concession: 3% to 8% based on progress
            concession_rate = 0.03 + 0.05 * (round_num / self.max_rounds)
            target_val = prev_val * (1 - concession_rate)
        else:
            # Reasonable initial offer: 70%
            target_val = self.total_value * 0.70
        
        # Don't concede too far below opponent's best offer
        if self.best_opp_value > 0:
            target_val = max(target_val, self.best_opp_value * 1.03)
        
        # Minimum floor
        target_val = max(target_val, self.total_value * 0.35)
        
        # Rank items by trade efficiency (my value / opponent value)
        items = []
        for i in range(self.num_types):
            if self.values[i] == 0:
                eff = -1
            elif self.opp_values[i] < 0.001:
                eff = float('inf')
            else:
                eff = self.values[i] / self.opp_values[i]
            items.append((eff, i))
        
        items.sort(key=lambda x: x[0], reverse=True)
        
        # Build offer greedily
        offer = [0] * self.num_types
        current_val = 0
        
        for eff, idx in items:
            if current_val >= target_val:
                break
            
            if self.values[idx] == 0:
                continue
            
            needed = target_val - current_val
            take = min(self.counts[idx], math.ceil(needed / self.values[idx]))
            
            offer[idx] = take
            current_val += take * self.values[idx]
        
        return offer