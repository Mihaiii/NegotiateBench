class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.rounds_remaining = max_rounds
        self.is_first = (me == 0)
        self.opponent_value_estimate = [1] * len(counts)
        self.opponent_offers = []
        self.min_acceptable_ratio = 0.5  # Start with 50% of total value as acceptable
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.rounds_remaining -= 1
        
        # Update opponent value estimates based on their offers
        if o is not None:
            self.opponent_offers.append(o.copy())
            self._update_opponent_estimates()
        
        # If it's our first turn, make an initial offer
        if o is None:
            return self._make_initial_offer()
        
        # Calculate current offer value to us
        our_value = sum(v * x for v, x in zip(self.values, o))
        
        # Calculate opponent's total value from this offer
        opponent_value = sum(self.opponent_value_estimate[i] * (self.counts[i] - o[i]) 
                            for i in range(len(self.counts)))
        total_opponent_value = sum(self.opponent_value_estimate[i] * self.counts[i] 
                                  for i in range(len(self.counts)))
        
        # Accept if this is good enough for us AND the opponent isn't getting too little
        min_accept = int(self.total_value * self.min_acceptable_ratio)
        
        # In later rounds, be more willing to accept slightly worse deals
        if self.rounds_remaining <= 2:
            min_accept = max(1, int(self.total_value * 0.35))
        
        if our_value >= min_accept and opponent_value >= total_opponent_value * 0.25:
            return None  # Accept
        
        # If opponent offers really low and we have few rounds left, accept even worse
        if self.rounds_remaining <= 1 and our_value >= 1:
            return None
            
        # Make counter-offer
        return self._make_counter_offer()
    
    def _update_opponent_estimates(self):
        """Estimate opponent valuations from their offers"""
        if not self.opponent_offers:
            return
            
        # Count how many times opponent kept each item type
        keep_counts = [0] * len(self.counts)
        
        for offer in self.opponent_offers:
            kept = [self.counts[i] - offer[i] for i in range(len(self.counts))]
            for i, k in enumerate(kept):
                if k > 0:
                    keep_counts[i] += 1
        
        # Normalize estimates to 1-10 scale
        max_keep = max(keep_counts) if max(keep_counts) > 0 else 1
        
        # Cap estimates to avoid extreme values
        self.opponent_value_estimate = [
            max(1, min(10, (k * 10) // max_keep)) for k in keep_counts
        ]
        
        # Update our acceptable threshold based on opponent behavior
        # If opponent is consistently demanding most, adjust our expectations down
        if len(self.opponent_offers) >= 3:
            avg_opponent_share = sum(
                sum(self.opponent_value_estimate[i] * (self.counts[i] - self.opponent_offers[j][i]) 
                    for i in range(len(self.counts))) /
                max(1, sum(self.opponent_value_estimate[i] * self.counts[i] 
                          for i in range(len(self.counts))))
                for j in range(len(self.opponent_offers))
            ) / len(self.opponent_offers)
            
            # If opponent is taking >70% on average, adjust our threshold down
            if avg_opponent_share > 0.70:
                self.min_acceptable_ratio = max(0.35, 1 - avg_opponent_share + 0.2)
    
    def _make_initial_offer(self) -> list[int]:
        """Create initial offer if we go first"""
        offer = [0] * len(self.counts)
        
        # Sort items by value ratio (our value / estimated opponent value)
        item_ratios = []
        for i in range(len(self.counts)):
            if self.opponent_value_estimate[i] == 0:
                ratio = float('inf')
            else:
                ratio = self.values[i] / self.opponent_value_estimate[i]
            item_ratios.append((i, ratio, self.values[i], self.opponent_value_estimate[i]))
        
        # Sort by ratio descending (items where we have relative advantage)
        item_ratios.sort(key=lambda x: x[1], reverse=True)
        
        # Target getting 60% of our value
        target_our_value = int(self.total_value * 0.6)
        current_our_value = 0
        
        # First, keep items we value highly relative to opponent
        for i, ratio, our_val, opp_val in item_ratios:
            if our_val >= opp_val:
                offer[i] = self.counts[i]
                current_our_value += self.counts[i] * our_val
            if current_our_value >= target_our_value:
                break
        
        # If we still need more value, take items where opponent values them less
        if current_our_value < target_our_value:
            for i, ratio, our_val, opp_val in item_ratios:
                if offer[i] < self.counts[i]:
                    take = min(self.counts[i] - offer[i], 
                              (target_our_value - current_our_value) // max(1, our_val) + 1)
                    offer[i] += take
                    current_our_value += take * our_val
                if current_our_value >= target_our_value:
                    break
        
        # Ensure we give opponent something (at least 1 item) if they value it
        for i, ratio, our_val, opp_val in item_ratios:
            if opp_val > 0 and self.counts[i] > 0 and offer[i] == self.counts[i]:
                offer[i] = max(0, self.counts[i] - 1)
                current_our_value -= our_val
                break  # Only give up one item
        
        return offer
    
    def _make_counter_offer(self) -> list[int]:
        """Create counter-offer after receiving opponent's offer"""
        offer = [0] * len(self.counts)
        
        # Sort items by value ratio
        item_ratios = []
        for i in range(len(self.counts)):
            if self.opponent_value_estimate[i] == 0:
                ratio = float('inf')
            else:
                ratio = self.values[i] / self.opponent_value_estimate[i]
            item_ratios.append((i, ratio, self.values[i], self.opponent_value_estimate[i]))
        
        item_ratios.sort(key=lambda x: x[1], reverse=True)
        
        # Adjust target based on rounds remaining
        if self.rounds_remaining <= 1:
            target_ratio = 0.50
        elif self.rounds_remaining <= 3:
            target_ratio = 0.55
        elif self.rounds_remaining <= 6:
            target_ratio = 0.60
        else:
            target_ratio = 0.65
            
        target_our_value = int(self.total_value * target_ratio)
        current_our_value = 0
        
        # First, take all items we value more than opponent
        for i, ratio, our_val, opp_val in item_ratios:
            if our_val > opp_val:
                offer[i] = self.counts[i]
                current_our_value += self.counts[i] * our_val
        
        # Then, if we still need more, take items where opponent values less
        if current_our_value < target_our_value:
            for i, ratio, our_val, opp_val in item_ratios:
                if offer[i] < self.counts[i]:
                    take = min(self.counts[i] - offer[i], 
                              (target_our_value - current_our_value) // max(1, our_val) + 1)
                    offer[i] += take
                    current_our_value += take * our_val
        
        # In very late rounds, make more concessions to ensure deal
        if self.rounds_remaining <= 1:
            # Try to match opponent's requested pattern more closely
            # Calculate what opponent is asking for in their latest offer
            if self.opponent_offers:
                latest = self.opponent_offers[-1]
                # Give them more of items they've consistently requested
                for i in range(len(offer)):
                    if latest[i] > 0 and self.values[i] <= self.opponent_value_estimate[i]:
                        offer[i] = min(self.counts[i], latest[i] + (self.counts[i] - latest[i]) // 2)
                        current_our_value = sum(offer[j] * self.values[j] for j in range(len(offer)))
                        break
        
        return offer