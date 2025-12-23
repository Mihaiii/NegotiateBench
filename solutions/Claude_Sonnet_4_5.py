class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        self.me = me
        self.their_offers = []
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_left = total_turns - self.turn_count + 1
        
        if o is not None:
            self.their_offers.append(o)
            my_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            if self._should_accept(my_value, turns_left):
                return None
        
        return self._make_offer(turns_left)
    
    def _should_accept(self, offered_value: int, turns_left: int) -> bool:
        """Accept offers based on value and urgency."""
        if turns_left <= 1:
            return offered_value > 0
        
        # Calculate what percentage of total value we're getting
        value_ratio = offered_value / self.total_value if self.total_value > 0 else 0
        
        # Acceptance threshold decreases as deadline approaches
        if turns_left <= 2:
            threshold = 0.25
        elif turns_left <= 4:
            threshold = 0.35
        elif turns_left <= 8:
            threshold = 0.40
        elif turns_left <= 16:
            threshold = 0.45
        else:
            threshold = 0.50
        
        if value_ratio >= threshold:
            return True
        
        # Try to infer if opponent is stuck/won't budge
        if len(self.their_offers) >= 4:
            recent_values = [sum(self.their_offers[i][j] * self.values[j] 
                               for j in range(len(self.values))) 
                           for i in range(-4, 0)]
            
            max_offered = max(recent_values)
            min_offered = min(recent_values)
            
            # If opponent's offers are stable and we're past halfway
            if max_offered - min_offered <= self.total_value * 0.05:
                if turns_left <= self.max_rounds and offered_value >= self.total_value * 0.30:
                    return True
        
        return False
    
    def _make_offer(self, turns_left: int) -> list[int]:
        """Make strategic offers that prioritize high-value items."""
        
        # Calculate target value ratio based on urgency
        if turns_left <= 2:
            target_ratio = 0.45
        elif turns_left <= 4:
            target_ratio = 0.50
        elif turns_left <= 8:
            target_ratio = 0.55
        elif turns_left <= 16:
            target_ratio = 0.60
        else:
            target_ratio = 0.65
        
        # Try to infer opponent's values from their offers
        opponent_likely_values = self._infer_opponent_values()
        
        # Generate offer that maximizes our value while giving opponent what they likely want
        offer = self._generate_strategic_offer(target_ratio, opponent_likely_values)
        
        return offer
    
    def _infer_opponent_values(self) -> list[float]:
        """Estimate what opponent values based on their offers."""
        if len(self.their_offers) < 2:
            # No info yet, assume they value items inversely to us
            return [1.0 / (v + 1) for v in self.values]
        
        # Count how often they request each item
        request_counts = [0] * len(self.counts)
        for offer in self.their_offers:
            for i in range(len(offer)):
                # They're requesting items NOT in their offer to us
                request_counts[i] += (self.counts[i] - offer[i])
        
        # Normalize to get estimated relative values
        total_requests = sum(request_counts) + 0.01  # Avoid division by zero
        return [r / total_requests for r in request_counts]
    
    def _generate_strategic_offer(self, target_ratio: float, opponent_values: list[float]) -> list[int]:
        """Generate offer that gets us high value while considering opponent's likely preferences."""
        target_value = target_ratio * self.total_value
        
        # Create items list with efficiency scores
        items = []
        for i in range(len(self.counts)):
            if self.counts[i] > 0:
                # How much we value it vs how much opponent likely values it
                my_val = self.values[i]
                their_val_estimate = opponent_values[i] * self.total_value
                
                # Efficiency: how much value we get vs how much opponent loses
                efficiency = my_val / (their_val_estimate + 1)
                items.append((efficiency, my_val, i))
        
        # Sort by efficiency - take items that are valuable to us but less so to them
        items.sort(reverse=True)
        
        offer = [0] * len(self.counts)
        current_value = 0
        
        # Greedy allocation prioritizing efficient items
        for efficiency, val, idx in items:
            for _ in range(self.counts[idx]):
                if current_value >= target_value:
                    break
                offer[idx] += 1
                current_value += val
        
        # If we haven't reached target, just take high-value items
        if current_value < target_value:
            high_val_items = sorted(range(len(self.values)), key=lambda i: self.values[i], reverse=True)
            for idx in high_val_items:
                while offer[idx] < self.counts[idx] and current_value < target_value:
                    offer[idx] += 1
                    current_value += self.values[idx]
        
        return offer