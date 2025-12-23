class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        self.offers_received = []
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        turns_left = self.max_rounds * 2 - self.turn_count + 1
        
        if o is not None:
            self.offers_received.append(o)
            my_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Dynamic acceptance threshold based on progress
            threshold = self._acceptance_threshold(turns_left, my_value)
            
            if my_value >= threshold:
                return None  # Accept
        
        # Generate strategic counter-offer
        return self._make_offer(turns_left)
    
    def _acceptance_threshold(self, turns_left: int, offered_value: int) -> float:
        """Calculate minimum acceptable value."""
        # Be more accepting as time runs out
        if turns_left <= 1:
            return 0  # Accept anything on last turn
        elif turns_left <= 2:
            return self.total_value * 0.35
        elif turns_left <= 4:
            return self.total_value * 0.45
        elif turns_left <= 8:
            return self.total_value * 0.5
        else:
            return self.total_value * 0.55
    
    def _estimate_opponent_values(self) -> list[float]:
        """Estimate opponent's values from their offers."""
        if not self.offers_received:
            # Assume opponent values items inversely to us
            return [1.0 / (v + 1) for v in self.values]
        
        # Analyze what opponent is keeping vs giving
        opp_estimates = [0.0] * len(self.counts)
        
        for offer in self.offers_received:
            for i in range(len(offer)):
                # What they keep suggests higher value
                they_keep = self.counts[i] - offer[i]
                opp_estimates[i] += they_keep
        
        # Normalize
        total = sum(opp_estimates) or 1
        return [e / total for e in opp_estimates]
    
    def _make_offer(self, turns_left: int) -> list[int]:
        """Generate a strategic offer."""
        # Target value decreases over time (concession strategy)
        if turns_left <= 2:
            target_ratio = 0.4
        elif turns_left <= 4:
            target_ratio = 0.5
        elif turns_left <= 8:
            target_ratio = 0.6
        else:
            target_ratio = 0.7
        
        target_value = target_ratio * self.total_value
        
        # Estimate opponent preferences
        opp_values = self._estimate_opponent_values()
        
        # Create items list with strategic scoring
        items = []
        for i in range(len(self.counts)):
            for _ in range(self.counts[i]):
                # Score: my value minus estimated opponent value
                # This helps us take items we value more and they value less
                my_val = self.values[i]
                opp_val = opp_values[i] * self.total_value / len(self.counts)
                score = my_val - opp_val * 0.5
                items.append((score, my_val, i))
        
        # Sort by strategic score
        items.sort(reverse=True)
        
        # Greedily select items
        offer = [0] * len(self.counts)
        current_value = 0
        
        for score, my_val, idx in items:
            offer[idx] += 1
            current_value += my_val
            
            if current_value >= target_value:
                break
        
        # Ensure we ask for something valuable
        if current_value < self.total_value * 0.3:
            # Fallback: take all items we value
            offer = [self.counts[i] if self.values[i] > 0 else 0 
                     for i in range(len(self.counts))]
        
        return offer