class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        self.me = me
        self.their_offers = []
        self.my_offers = []
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_left = total_turns - self.turn_count + 1
        
        if o is not None:
            self.their_offers.append(o)
            my_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            if self._should_accept(my_value, turns_left):
                return None
        
        new_offer = self._make_offer(turns_left)
        self.my_offers.append(new_offer)
        return new_offer
    
    def _should_accept(self, offered_value: int, turns_left: int) -> bool:
        """Dynamic acceptance based on value, urgency, and opponent behavior."""
        if turns_left <= 1:
            return offered_value > 0
        
        value_ratio = offered_value / self.total_value if self.total_value > 0 else 0
        
        # Progressive threshold that decreases over time
        progress = 1 - (turns_left / (self.max_rounds * 2))
        base_threshold = 0.55 - (progress * 0.25)  # 0.55 -> 0.30
        
        # Adjust threshold based on opponent behavior
        if len(self.their_offers) >= 3:
            recent_values = [sum(self.their_offers[i][j] * self.values[j] 
                               for j in range(len(self.values))) 
                           for i in range(-3, 0)]
            
            # If opponent is making concessions, wait a bit more
            if recent_values[-1] > recent_values[0]:
                base_threshold += 0.05
            
            # If opponent is stuck on same offer, be more willing to accept
            if max(recent_values) - min(recent_values) <= self.total_value * 0.03:
                base_threshold -= 0.10
                
                # Detect if we're also stuck - avoid deadlock
                if len(self.my_offers) >= 3:
                    my_values = [sum(self.my_offers[i][j] * self.values[j] 
                                   for j in range(len(self.values))) 
                               for i in range(-3, 0)]
                    if max(my_values) - min(my_values) <= self.total_value * 0.03:
                        # Both stuck - accept if reasonable
                        if value_ratio >= 0.35 or turns_left <= 4:
                            return True
        
        # More aggressive acceptance as deadline approaches
        if turns_left <= 2:
            return value_ratio >= 0.25
        elif turns_left <= 4:
            return value_ratio >= base_threshold - 0.10
        
        return value_ratio >= base_threshold
    
    def _make_offer(self, turns_left: int) -> list[int]:
        """Strategic offers with gradual concessions."""
        progress = 1 - (turns_left / (self.max_rounds * 2))
        
        # Start high, concede gradually
        target_ratio = 0.70 - (progress * 0.25)  # 0.70 -> 0.45
        
        # Accelerate concessions near deadline
        if turns_left <= 4:
            target_ratio = max(0.40, target_ratio - 0.05)
        
        # Infer opponent preferences from their offers
        opponent_values = self._estimate_opponent_values()
        
        return self._optimize_offer(target_ratio, opponent_values)
    
    def _estimate_opponent_values(self) -> list[float]:
        """Estimate opponent's valuation from their offer patterns."""
        if len(self.their_offers) < 2:
            # Default: assume inverse correlation with our values
            max_val = max(self.values) + 1
            return [max_val - v for v in self.values]
        
        # Track what they consistently keep for themselves
        kept_counts = [0] * len(self.counts)
        for offer in self.their_offers:
            for i in range(len(offer)):
                kept_counts[i] += (self.counts[i] - offer[i])
        
        # Normalize to estimate relative values
        total = sum(kept_counts) + 0.01
        return [k / total * self.total_value for k in kept_counts]
    
    def _optimize_offer(self, target_ratio: float, opp_values: list[float]) -> list[int]:
        """Generate offer maximizing our value while considering opponent."""
        target_value = target_ratio * self.total_value
        
        # Score each item by efficiency: our_value / opponent_value
        items = []
        for i in range(len(self.counts)):
            for _ in range(self.counts[i]):
                efficiency = self.values[i] / (opp_values[i] + 0.1)
                items.append((efficiency, self.values[i], i))
        
        # Sort by efficiency - take items valuable to us, less to them
        items.sort(reverse=True)
        
        offer = [0] * len(self.counts)
        current_value = 0
        
        # Greedy allocation
        for efficiency, val, idx in items:
            if current_value >= target_value:
                break
            offer[idx] += 1
            current_value += val
        
        # If under target, add highest value items
        if current_value < target_value:
            for i in sorted(range(len(self.values)), 
                          key=lambda x: self.values[x], reverse=True):
                while offer[i] < self.counts[i] and current_value < target_value:
                    offer[i] += 1
                    current_value += self.values[i]
        
        return offer