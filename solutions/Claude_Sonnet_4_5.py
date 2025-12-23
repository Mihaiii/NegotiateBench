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
        """Decide whether to accept an offer."""
        if turns_left <= 1:
            return offered_value > 0
        
        # Dynamic threshold based on game stage
        if turns_left <= 2:
            threshold = 0.15  # Accept almost anything at the end
        elif turns_left <= 4:
            threshold = 0.25
        elif turns_left <= 6:
            threshold = 0.33
        elif turns_left <= 10:
            threshold = 0.40
        else:
            threshold = 0.50
        
        # Check if opponent is making concessions
        if len(self.their_offers) >= 2:
            prev_value = sum(self.their_offers[-2][i] * self.values[i] for i in range(len(self.values)))
            if offered_value > prev_value:
                # They're conceding, accept if reasonable
                if offered_value >= self.total_value * max(0.30, threshold - 0.10):
                    return True
        
        # Check for stubbornness - if they keep offering the same, adapt
        if len(self.their_offers) >= 4:
            recent_values = [sum(self.their_offers[i][j] * self.values[j] 
                                for j in range(len(self.values))) 
                            for i in range(-4, 0)]
            
            # If offers are stable and time is running out
            if max(recent_values) - min(recent_values) <= self.total_value * 0.05:
                if turns_left <= 8 and offered_value >= self.total_value * 0.30:
                    return True
                if turns_left <= 4 and offered_value >= self.total_value * 0.20:
                    return True
        
        return offered_value >= self.total_value * threshold
    
    def _estimate_opponent_values(self) -> list[int]:
        """Estimate opponent's valuation from their offers."""
        if not self.their_offers:
            # Initially assume inverse preferences
            return [max(self.values) - v + 1 for v in self.values]
        
        n = len(self.counts)
        kept_ratio = [0.0] * n
        
        # Analyze what they typically keep
        for offer in self.their_offers:
            for i in range(n):
                if self.counts[i] > 0:
                    kept_ratio[i] += (self.counts[i] - offer[i]) / self.counts[i]
        
        # Normalize to sum to total_value
        total_kept = sum(kept_ratio) or 1
        estimated = [int(self.total_value * (kept_ratio[i] / total_kept)) 
                    for i in range(n)]
        
        return estimated
    
    def _make_offer(self, turns_left: int) -> list[int]:
        """Generate strategic counter-offer."""
        # Target value decreases as deadline approaches
        if turns_left <= 2:
            target_ratio = 0.35
        elif turns_left <= 4:
            target_ratio = 0.40
        elif turns_left <= 6:
            target_ratio = 0.45
        elif turns_left <= 10:
            target_ratio = 0.50
        else:
            # Start aggressive
            target_ratio = 0.65
        
        # Analyze opponent behavior
        if len(self.their_offers) >= 3:
            recent = self.their_offers[-3:]
            values = [sum(o[i] * self.values[i] for i in range(len(o))) for o in recent]
            
            # If opponent is stubborn (not changing offers much)
            if max(values) - min(values) <= self.total_value * 0.05:
                best_offer = max(values)
                # If their best offer is reasonable, concede more to reach a deal
                if best_offer >= self.total_value * 0.25:
                    target_ratio = min(target_ratio, 0.55)
        
        target_value = target_ratio * self.total_value
        
        # Get opponent value estimates
        opp_values = self._estimate_opponent_values()
        
        # Create items sorted by strategic value
        items = []
        for i in range(len(self.counts)):
            for _ in range(self.counts[i]):
                # Priority: my value minus opportunity cost (opponent's value)
                priority = self.values[i] - (opp_values[i] * 0.3)
                items.append((priority, self.values[i], i))
        
        items.sort(reverse=True)
        
        # Build offer greedily
        offer = [0] * len(self.counts)
        current_value = 0
        
        for priority, my_val, idx in items:
            if current_value >= target_value:
                break
            offer[idx] += 1
            current_value += my_val
        
        # Ensure minimum reasonable offer
        if current_value < self.total_value * 0.25:
            offer = [self.counts[i] if self.values[i] > 0 else 0 
                    for i in range(len(self.counts))]
        
        # In late game, ensure we're not too greedy
        if turns_left <= 3:
            offer_value = sum(offer[i] * self.values[i] for i in range(len(offer)))
            if offer_value > self.total_value * 0.55:
                # Scale back proportionally
                for i in range(len(offer)):
                    if offer[i] > 0 and self.values[i] > 0:
                        # Keep at most 70% of items we value
                        max_keep = max(1, int(self.counts[i] * 0.7))
                        offer[i] = min(offer[i], max_keep)
        
        return offer