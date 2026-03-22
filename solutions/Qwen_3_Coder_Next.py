class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # State tracking
        self.round_num = 0
        self.opponent_history = []
        self.our_history = []
        self.opponent_values = None
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        # Update round counter - increment when we receive an offer from opponent
        if o is not None:
            self.opponent_history.append(o.copy())
            self.round_num += 1
        
        # Calculate remaining rounds after this turn
        rounds_after = self.max_rounds - self.round_num
        
        # Estimate opponent values if we haven't yet
        if self.opponent_values is None:
            self.opponent_values = self._estimate_opponent_values()
        
        # Calculate our value for current opponent offer
        if o is not None:
            our_value = sum(v * x for v, x in zip(self.values, o))
        else:
            our_value = None
        
        # Determine if we should accept
        if o is not None and self._should_accept(o, rounds_after, our_value):
            return None
            
        # Make our offer
        return self._make_offer(rounds_after)
    
    def _should_accept(self, opponent_offer: list[int], rounds_after: int, our_value: int) -> bool:
        """Determine if we should accept the opponent's offer."""
        if rounds_after < 0:
            return True  # Last round, must accept
            
        # If we're the second mover (me == 1) and it's the final round, accept if positive value
        if self.me == 1 and rounds_after == 0 and our_value > 0:
            return True
            
        # Calculate reservation value based on remaining rounds
        # As rounds decrease, lower our standards
        if rounds_after == 0:
            # Final round for us - accept any positive value
            return our_value > 0
            
        # Calculate expected value if we continue
        # Assume we can get at least 40-60% of total value depending on position
        if self.me == 0:  # First mover advantage
            expected_future_value = self.total_value * (0.55 - 0.05 * (self.round_num / self.max_rounds))
        else:  # Second mover - more patience
            expected_future_value = self.total_value * (0.50 - 0.03 * (self.round_num / self.max_rounds))
            
        return our_value >= expected_future_value
    
    def _estimate_opponent_values(self) -> list[int]:
        """Estimate opponent valuations from their offers."""
        n_items = len(self.counts)
        
        # Initialize with uniform estimate
        estimate = [1] * n_items
        
        if not self.opponent_history:
            return estimate
            
        # Analyze what the opponent kept in their offers
        # Higher count kept = likely more valuable to opponent
        for i in range(n_items):
            kept_totals = []
            
            for offer in self.opponent_history:
                kept = self.counts[i] - offer[i]
                kept_totals.append(kept)
            
            # If opponent consistently keeps many items of this type, they likely value it
            avg_kept = sum(kept_totals) / len(kept_totals)
            
            # Scale estimates 0-3 based on average kept
            if avg_kept > self.counts[i] * 0.7:
                estimate[i] = 3
            elif avg_kept > self.counts[i] * 0.4:
                estimate[i] = 2
            elif avg_kept > 0:
                estimate[i] = 1
                
        # Refine: if opponent keeps items we value, they likely value them more
        for i in range(n_items):
            if self.values[i] > 0:
                # Count how many times opponent refused to give us this item
                refusals = sum(1 for offer in self.opponent_history if offer[i] == 0)
                if refusals > len(self.opponent_history) * 0.6:
                    estimate[i] = max(estimate[i], 2)
                    
        # Ensure no item has zero estimate if it's available
        for i in range(n_items):
            if self.counts[i] > 0 and estimate[i] == 0:
                estimate[i] = 1
                
        return estimate
    
    def _make_offer(self, rounds_after: int) -> list[int]:
        """Create a strategic offer."""
        n_items = len(self.counts)
        
        # Calculate what we need to give opponent to make it attractive
        opponent_total = sum(c * v for c, v in zip(self.counts, self.opponent_values))
        
        # Target split ratio based on position and remaining rounds
        if self.me == 0:  # First mover
            # Can be more aggressive early, become fairer later
            opponent_share = 0.45 - 0.03 * (self.round_num / self.max_rounds) + 0.02 * (1 - rounds_after / self.max_rounds)
        else:  # Second mover
            # Can be more demanding since we've seen their offers
            opponent_share = 0.45 - 0.02 * (self.round_num / self.max_rounds) + 0.03 * (1 - rounds_after / self.max_rounds)
            
        # Ensure reasonable bounds
        opponent_share = max(0.3, min(0.6, opponent_share))
        
        opponent_target = int(opponent_total * opponent_share)
        
        # Build offer - give opponent items they value most but we value least
        offer = [0] * n_items
        
        # Sort items by: opponent value / our value (if we value it)
        # Items we don't value but opponent does should go to them first
        item_priority = []
        for i in range(n_items):
            if self.values[i] == 0 and self.opponent_values[i] > 0:
                # Perfect item to give - we don't want, opponent wants
                priority = float('inf')
            elif self.values[i] > 0 and self.opponent_values[i] == 0:
                # Perfect item to keep - we want, opponent doesn't
                priority = float('-inf')
            elif self.opponent_values[i] == 0:
                # Opponent doesn't want, give minimal amount
                priority = 0
            else:
                # Balance item - opponent wants more than we do
                priority = self.opponent_values[i] / max(1, self.values[i])
            item_priority.append((priority, i))
            
        item_priority.sort(reverse=True)
        
        # Allocate to opponent
        opponent_got = 0
        for _, i in item_priority:
            if opponent_got >= opponent_target:
                break
                
            # Avoid giving items we value highly unless opponent desperately wants them
            if self.values[i] > 3 and self.opponent_values[i] <= 1:
                continue
                
            # Give all items of this type to opponent
            offer[i] = self.counts[i]
            opponent_got += self.counts[i] * self.opponent_values[i]
        
        # If we still need to give more value, be more selective
        if opponent_got < opponent_target:
            for _, i in item_priority:
                if opponent_got >= opponent_target:
                    break
                if offer[i] < self.counts[i] and self.opponent_values[i] > 0:
                    needed = opponent_target - opponent_got
                    add_count = min(self.counts[i] - offer[i], 
                                  (needed + self.opponent_values[i] - 1) // self.opponent_values[i])
                    offer[i] += add_count
                    opponent_got += add_count * self.opponent_values[i]
        
        # Validate - ensure we don't end with zero value
        our_value_in_offer = sum(v * x for v, x in zip(self.values, offer))
        if our_value_in_offer == 0 and self.total_value > 0:
            # Keep at least one valuable item
            best_item = max(range(n_items), key=lambda i: self.values[i])
            offer[best_item] = max(offer[best_item], min(1, self.counts[best_item]))
            
        return offer