class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        self.opponent_offers = []
        self.inferred_opponent_values = [1] * len(values)  # Start with neutral assumptions
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_remaining = total_turns - self.turn_count + 1
        
        # Handle opponent's offer
        if o is not None:
            # Validate offer
            valid = True
            offer_value = 0
            for i in range(len(o)):
                if o[i] < 0 or o[i] > self.counts[i]:
                    valid = False
                    break
                offer_value += o[i] * self.values[i]
            
            if not valid:
                return None
                
            # Store opponent's offer for inference
            self.opponent_offers.append(o)
            self._update_inferred_values(o)
            
            # Calculate what we should accept based on remaining time and inferred dynamics
            if turns_remaining == 1:
                # Last turn - accept anything better than nothing
                if offer_value > 0:
                    return None
            else:
                # Be more flexible as time runs out
                time_pressure_factor = min(1.0, (total_turns - turns_remaining + 1) / total_turns)
                min_acceptable = self.total_value * (0.3 + 0.2 * time_pressure_factor)
                
                if offer_value >= min_acceptable:
                    return None
        
        # Generate counter-offer based on inferred opponent preferences
        return self._generate_strategic_offer(turns_remaining)
    
    def _update_inferred_values(self, opponent_offer: list[int]):
        """Infer opponent's valuations based on what they keep for themselves"""
        # What opponent keeps = total - what they offer to us
        opponent_keeps = [self.counts[i] - opponent_offer[i] for i in range(len(self.counts))]
        
        # Update inferred values - if opponent keeps many of an item, they likely value it highly
        for i in range(len(self.counts)):
            if self.counts[i] > 0:
                # Normalize by count to get per-item preference
                keep_ratio = opponent_keeps[i] / self.counts[i]
                # Update with exponential moving average
                self.inferred_opponent_values[i] = max(0.1, 
                    0.7 * self.inferred_opponent_values[i] + 0.3 * (keep_ratio + 0.1))
    
    def _generate_strategic_offer(self, turns_remaining: int) -> list[int]:
        """Generate an offer that balances our value with strategic concessions"""
        total_turns = self.max_rounds * 2
        time_pressure = min(1.0, (total_turns - turns_remaining + 1) / total_turns)
        
        # Start with a reasonable baseline - don't demand everything
        if self.turn_count == 1:
            # First move: be reasonably generous to start negotiation
            target_value_ratio = 0.7 - 0.2 * time_pressure
        else:
            # Later moves: adjust based on time pressure
            target_value_ratio = 0.6 - 0.3 * time_pressure
        
        target_value = self.total_value * target_value_ratio
        
        # Create initial proposal prioritizing our high-value items
        proposal = [0] * len(self.counts)
        current_value = 0
        
        # First, take items we value highly
        item_indices = sorted(range(len(self.values)), key=lambda i: self.values[i], reverse=True)
        
        for i in item_indices:
            if self.values[i] > 0:
                # Take as many as needed to reach target, but be reasonable
                max_to_take = self.counts[i]
                if current_value < target_value:
                    # Take most of it initially
                    take_amount = max_to_take
                    proposal[i] = take_amount
                    current_value += take_amount * self.values[i]
                else:
                    # Don't take items we don't need for target
                    proposal[i] = 0
        
        # If we're way over target, reduce on items that opponent might value highly
        if current_value > target_value * 1.2:
            # Find items where opponent likely values more than us (relative)
            item_ratios = []
            for i in range(len(self.counts)):
                if self.values[i] > 0 and self.inferred_opponent_values[i] > 0:
                    ratio = self.inferred_opponent_values[i] / (self.values[i] + 0.1)
                    item_ratios.append((ratio, i))
            
            # Sort by opponent preference ratio (highest first)
            item_ratios.sort(reverse=True)
            
            # Reduce our take on items opponent values highly
            for ratio, i in item_ratios:
                if current_value <= target_value * 1.1:
                    break
                if proposal[i] > 0:
                    reduction = min(proposal[i], max(1, int((current_value - target_value * 1.1) / self.values[i])))
                    proposal[i] -= reduction
                    current_value -= reduction * self.values[i]
        
        # Handle items we don't value (values[i] == 0)
        for i in range(len(self.counts)):
            if self.values[i] == 0:
                # Give these to opponent unless we have reason to think they don't value them
                if self.inferred_opponent_values[i] > 0.5:
                    proposal[i] = 0
                else:
                    # If opponent seems to not value it either, we can take it (doesn't hurt us)
                    proposal[i] = self.counts[i]
        
        # Ensure validity
        for i in range(len(proposal)):
            proposal[i] = max(0, min(proposal[i], self.counts[i]))
        
        return proposal