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
        """Accept based on value and urgency."""
        if self.total_value == 0:
            return True
            
        value_ratio = offered_value / self.total_value
        
        # Last chance - accept anything positive
        if turns_left <= 1:
            return offered_value > 0
        
        # Time-based threshold that decreases more aggressively
        progress = 1 - (turns_left / (self.max_rounds * 2))
        base_threshold = 0.52 - (progress * 0.22)  # 0.52 -> 0.30
        
        # Analyze opponent behavior
        if len(self.their_offers) >= 2:
            recent_values = [sum(self.their_offers[i][j] * self.values[j] 
                               for j in range(len(self.values))) 
                           for i in range(-min(3, len(self.their_offers)), 0)]
            
            # If opponent is improving offers, wait slightly
            if len(recent_values) >= 2 and recent_values[-1] > recent_values[0]:
                base_threshold += 0.03
            
            # Detect stalemate - both stuck on same offers
            if len(recent_values) >= 2:
                variance = max(recent_values) - min(recent_values)
                if variance <= self.total_value * 0.05:
                    # Check if we're also stuck
                    if len(self.my_offers) >= 2:
                        my_values = [sum(self.my_offers[i][j] * self.values[j] 
                                       for j in range(len(self.values))) 
                                   for i in range(-min(3, len(self.my_offers)), 0)]
                        my_variance = max(my_values) - min(my_values)
                        
                        # Both stuck - break deadlock
                        if my_variance <= self.total_value * 0.05:
                            if value_ratio >= 0.40 or turns_left <= 3:
                                return True
        
        # Urgency-based acceptance
        if turns_left <= 2:
            return value_ratio >= 0.30
        elif turns_left <= 4:
            return value_ratio >= base_threshold - 0.08
        
        return value_ratio >= base_threshold
    
    def _make_offer(self, turns_left: int) -> list[int]:
        """Generate strategic offer."""
        progress = 1 - (turns_left / (self.max_rounds * 2))
        
        # Start at 60%, gradually decrease to 45%
        target_ratio = 0.60 - (progress * 0.15)
        
        # More aggressive concessions near end
        if turns_left <= 3:
            target_ratio = max(0.42, target_ratio - 0.05)
        elif turns_left <= 5:
            target_ratio = max(0.45, target_ratio - 0.03)
        
        # Estimate opponent values
        opp_values = self._estimate_opponent_values()
        
        return self._optimize_offer(target_ratio, opp_values)
    
    def _estimate_opponent_values(self) -> list[float]:
        """Infer opponent's valuation from their offers."""
        if len(self.their_offers) < 2:
            # Assume complementary preferences
            total = sum(self.values) + 1
            return [(total - v) / len(self.values) for v in self.values]
        
        # Analyze what they consistently keep
        kept_totals = [0.0] * len(self.counts)
        for offer in self.their_offers:
            for i in range(len(offer)):
                # What they keep for themselves
                kept_totals[i] += (self.counts[i] - offer[i])
        
        # Weight recent offers more
        if len(self.their_offers) >= 3:
            for i in range(len(self.their_offers[-2:])):
                offer = self.their_offers[-(i+1)]
                for j in range(len(offer)):
                    kept_totals[j] += (self.counts[j] - offer[j]) * (i + 1)
        
        # Normalize
        total = sum(kept_totals) + 0.01
        estimated = [k / total * self.total_value for k in kept_totals]
        
        return estimated
    
    def _optimize_offer(self, target_ratio: float, opp_values: list[float]) -> list[int]:
        """Create offer maximizing our value while being acceptable."""
        target_value = target_ratio * self.total_value
        
        # Create list of all items with efficiency scores
        items = []
        for i in range(len(self.counts)):
            for _ in range(self.counts[i]):
                # Prioritize items valuable to us, less to opponent
                efficiency = self.values[i] / (opp_values[i] + 0.1)
                items.append((efficiency, self.values[i], i))
        
        # Sort by efficiency
        items.sort(reverse=True, key=lambda x: (x[0], x[1]))
        
        offer = [0] * len(self.counts)
        current_value = 0
        
        # Greedy allocation
        for efficiency, val, idx in items:
            if current_value >= target_value:
                break
            offer[idx] += 1
            current_value += val
        
        # Ensure we get at least target value
        if current_value < target_value:
            for i in sorted(range(len(self.values)), 
                          key=lambda x: self.values[x], reverse=True):
                while offer[i] < self.counts[i] and current_value < target_value:
                    offer[i] += 1
                    current_value += self.values[i]
        
        return offer