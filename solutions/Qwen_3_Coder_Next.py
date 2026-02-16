class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.rounds_remaining = max_rounds
        self.is_first = (me == 0)
        self.opponent_offer_history = []
        self.opponent_counts = counts.copy()  # Initial assumption: opponent has all items
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.rounds_remaining -= 1
        
        # Update opponent history if we received an offer
        if o is not None:
            # Store opponent's offer (what they're willing to give us)
            self.opponent_offer_history.append(o.copy())
            
            # Infer opponent's valuations from their behavior
            # If they keep offering the same pattern, they likely value those items
            self._update_opponent_valuations()
        
        # If it's our first turn (no offer to respond to)
        if o is None:
            return self._make_initial_offer()
        
        # Calculate current offer value to us
        our_value = sum(v * x for v, x in zip(self.values, o))
        
        # Estimate what opponent might accept
        opponent_estimate = self._estimate_opponent_acceptable()
        
        # Calculate discount factor based on rounds remaining
        discount = 0.95 ** max(0, self.rounds_remaining)
        
        # Accept if offer is good enough relative to future discount
        min_accept_value = self.total_value * 0.40 * discount + 1
        
        if our_value >= min_accept_value:
            return None  # Accept
            
        # If opponent's offer is really bad and we have few rounds left, accept slightly worse
        if self.rounds_remaining <= 1 and our_value > 0:
            return None
            
        # Make a counter-offer
        return self._make_counter_offer()

    def _update_opponent_valuations(self):
        """Refine opponent valuation estimates based on their offers"""
        if not self.opponent_offer_history:
            return
            
        # Simple heuristic: items opponent keeps consistently are likely high value to them
        # Count how many times opponent kept each item type across offers
        keep_counts = [0] * len(self.counts)
        
        for offer in self.opponent_offer_history:
            # Opponent keeps what we don't get
            kept = [self.counts[i] - offer[i] for i in range(len(self.counts))]
            for i, k in enumerate(kept):
                if k > 0:
                    keep_counts[i] += 1
        
        # Use these counts to estimate opponent values
        # Normalize to 1-10 scale
        max_count = max(keep_counts) if max(keep_counts) > 0 else 1
        
        self.opponent_values = []
        for i, count in enumerate(keep_counts):
            if max_count > 0:
                val = max(1, int(count * 10 / max_count))
            else:
                val = 1
            self.opponent_values.append(val)
    
    def _estimate_opponent_acceptable(self) -> float:
        """Estimate minimum value opponent would accept"""
        # In early rounds, opponent likely wants >40% of their value
        # In late rounds, they become more flexible
        if self.rounds_remaining >= 5:
            return 0.45
        elif self.rounds_remaining >= 2:
            return 0.40
        else:
            return 0.35
    
    def _make_initial_offer(self) -> list[int]:
        """Create initial offer if we go first"""
        # Estimate opponent valuations
        if not hasattr(self, 'opponent_values'):
            self.opponent_values = [1] * len(self.counts)
            
        # Sort items by our value vs their value ratio (high ratio = good for us)
        item_ratios = []
        for i in range(len(self.counts)):
            if self.opponent_values[i] == 0:
                ratio = float('inf')
            else:
                ratio = self.values[i] / max(self.opponent_values[i], 1)
            item_ratios.append((i, ratio, self.values[i], self.opponent_values[i]))
        
        # Sort by ratio (high ratio items are better for us to keep)
        item_ratios.sort(key=lambda x: x[1], reverse=True)
        
        # Try to get 60% of our total value while giving opponent ~40% of theirs
        target_our_value = int(self.total_value * 0.6)
        
        offer = [0] * len(self.counts)
        current_our_value = 0
        current_opponent_value = 0
        
        # First, give opponent items they value highly (even if we value them moderately)
        for i, ratio, our_val, opp_val in item_ratios:
            if opp_val >= our_val:
                # Give opponent all items they value at least as much as we do
                offer[i] = 0  # We get 0, opponent gets all
                current_opponent_value += opp_val * self.counts[i]
        
        # Then, keep items we value highly and opponent values low
        for i, ratio, our_val, opp_val in item_ratios:
            if offer[i] == 0:  # Still need to assign
                # Give opponent some but keep most if we value it much more
                if our_val > opp_val * 2:  # We value much more
                    # Keep 70% of this item type
                    keep = int(self.counts[i] * 0.7)
                    offer[i] = keep
                    current_our_value += keep * our_val
                else:
                    # Split more evenly
                    keep = int(self.counts[i] * 0.5)
                    offer[i] = keep
                    current_our_value += keep * our_val
        
        # Fine-tune to get closer to 60% target
        if current_our_value < target_our_value:
            # Try to keep more high-value items
            for i, ratio, our_val, opp_val in item_ratios:
                if offer[i] > 0 and current_our_value < target_our_value:
                    increase = min(offer[i], (self.counts[i] - offer[i]))
                    offer[i] += increase
                    current_our_value += increase * our_val
        
        # Ensure we're not taking all items from opponent if they value them highly
        for i in range(len(offer)):
            # Always give opponent at least 1 item if they have any
            if self.counts[i] > 0 and self.opponent_values[i] > 3:
                if offer[i] == self.counts[i]:  # We're taking all
                    offer[i] = max(0, self.counts[i] - 1)
        
        return offer
    
    def _make_counter_offer(self) -> list[int]:
        """Create counter-offer after receiving opponent's offer"""
        if not hasattr(self, 'opponent_values'):
            self.opponent_values = [1] * len(self.counts)
            
        # Sort items by our value vs their value ratio
        item_ratios = []
        for i in range(len(self.counts)):
            if self.opponent_values[i] == 0:
                ratio = float('inf')
            else:
                ratio = self.values[i] / max(self.opponent_values[i], 1)
            item_ratios.append((i, ratio, self.values[i], self.opponent_values[i]))
        item_ratios.sort(key=lambda x: x[1], reverse=True)
        
        # Determine how generous to be based on rounds remaining
        if self.rounds_remaining <= 2:
            target_ratio = 0.55  # In late rounds, aim for 55% for us
        elif self.rounds_remaining <= 5:
            target_ratio = 0.60  # Mid rounds, aim for 60%
        else:
            target_ratio = 0.65  # Early rounds, be greedy but fair
        
        target_our_value = int(self.total_value * target_ratio)
        
        offer = [0] * len(self.counts)
        current_our_value = 0
        
        # First, take all items we value highly and opponent values low
        for i, ratio, our_val, opp_val in item_ratios:
            if our_val > opp_val:
                # Take most of items we value more
                take = int(self.counts[i] * 0.7) + (1 if our_val > opp_val * 2 else 0)
                offer[i] = min(take, self.counts[i])
                current_our_value += offer[i] * our_val
        
        # Then, take some items where values are balanced
        for i, ratio, our_val, opp_val in item_ratios:
            if offer[i] == 0 and current_our_value < target_our_value:
                # Take a moderate amount
                take = int(self.counts[i] * 0.5)
                offer[i] = min(take, self.counts[i])
                current_our_value += offer[i] * our_val
        
        # Finally, take items opponent values less if needed
        while current_our_value < target_our_value:
            made_change = False
            for i, ratio, our_val, opp_val in item_ratios:
                if offer[i] < self.counts[i] and current_our_value < target_our_value:
                    offer[i] += 1
                    current_our_value += our_val
                    made_change = True
                    break
            if not made_change:
                break
        
        # Make sure we're not being too greedy in very late rounds
        if self.rounds_remaining <= 1 and current_our_value > self.total_value * 0.7:
            # Reduce our take
            for i, ratio, our_val, opp_val in item_ratios:
                if offer[i] > 0 and current_our_value > self.total_value * 0.65:
                    reduce_by = min(offer[i], (offer[i] + 1) // 2)
                    offer[i] -= reduce_by
                    current_our_value -= reduce_by * our_val
        
        return offer