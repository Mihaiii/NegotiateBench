class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        self.my_offers = []
        self.their_offers = []
        self.me = me
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_left = total_turns - self.turn_count + 1
        
        if o is not None:
            self.their_offers.append(o)
            my_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Accept based on strategic threshold
            if self._should_accept(my_value, turns_left):
                return None
        
        # Generate counter-offer
        counter = self._make_offer(turns_left)
        self.my_offers.append(counter)
        return counter
    
    def _should_accept(self, offered_value: int, turns_left: int) -> bool:
        """Decide whether to accept an offer."""
        if turns_left <= 1:
            # Last turn - accept anything positive
            return offered_value > 0
        
        # Calculate base threshold that decreases over time
        progress = 1.0 - (turns_left / (self.max_rounds * 2))
        
        # Start at 60% and decrease to 30%
        base_threshold = 0.6 - (0.3 * progress)
        
        # Check if opponent is making concessions
        if len(self.their_offers) >= 2:
            prev_value = sum(self.their_offers[-2][i] * self.values[i] for i in range(len(self.values)))
            if offered_value > prev_value:
                # They're conceding, be slightly more demanding
                base_threshold += 0.05
            elif offered_value < prev_value and turns_left <= 4:
                # They're getting tougher near the end, be flexible
                base_threshold -= 0.1
        
        # Near the end, be more accepting
        if turns_left <= 3:
            base_threshold = min(base_threshold, 0.35)
        if turns_left <= 2:
            base_threshold = min(base_threshold, 0.25)
        
        return offered_value >= self.total_value * base_threshold
    
    def _estimate_opponent_values(self) -> list[int]:
        """Estimate opponent's valuation of each item type."""
        if not self.their_offers:
            # Default: assume inverse preferences
            total = sum(self.values) or 1
            return [max(1, total - v) for v in self.values]
        
        # Analyze what they consistently keep
        kept_counts = [0] * len(self.counts)
        for offer in self.their_offers:
            for i in range(len(offer)):
                kept_counts[i] += self.counts[i] - offer[i]
        
        # Items they keep more are likely more valuable to them
        # Normalize to total_value
        total_kept = sum(kept_counts) or 1
        estimated = [int(self.total_value * k / total_kept) for k in kept_counts]
        
        # Ensure total matches
        current_total = sum(estimated[i] * self.counts[i] for i in range(len(estimated)))
        if current_total > 0:
            scale = self.total_value / current_total
            estimated = [max(0, int(e * scale)) for e in estimated]
        
        return estimated
    
    def _make_offer(self, turns_left: int) -> list[int]:
        """Generate a strategic counter-offer."""
        # Calculate target value based on time pressure
        progress = 1.0 - (turns_left / (self.max_rounds * 2))
        
        # Start aggressive (70%) and concede to fair (50%)
        if turns_left <= 2:
            target_ratio = 0.45
        elif turns_left <= 4:
            target_ratio = 0.50
        elif turns_left <= 8:
            target_ratio = 0.55
        else:
            target_ratio = 0.65 - (0.10 * progress)
        
        # If opponent is being very stubborn, concede faster
        if len(self.their_offers) >= 3:
            recent_offers = self.their_offers[-3:]
            values = [sum(o[i] * self.values[i] for i in range(len(o))) for o in recent_offers]
            if max(values) - min(values) < self.total_value * 0.05:
                # They're not budging much, concede more
                target_ratio -= 0.1
        
        target_value = target_ratio * self.total_value
        
        # Estimate what opponent values
        opp_values = self._estimate_opponent_values()
        
        # Build priority list: prefer items high value to us, low to them
        items = []
        for i in range(len(self.counts)):
            for _ in range(self.counts[i]):
                my_val = self.values[i]
                opp_val = opp_values[i]
                # Prioritize items valuable to me and cheap for opponent
                priority = my_val * 2 - opp_val
                items.append((priority, my_val, i))
        
        items.sort(reverse=True)
        
        # Greedily select items
        offer = [0] * len(self.counts)
        current_value = 0
        
        for priority, my_val, idx in items:
            if current_value >= target_value:
                break
            offer[idx] += 1
            current_value += my_val
        
        # Ensure we're asking for something reasonable
        if current_value < self.total_value * 0.3:
            # Fallback: take items we value
            offer = [self.counts[i] if self.values[i] > 0 else 0 
                     for i in range(len(self.counts))]
        
        return offer