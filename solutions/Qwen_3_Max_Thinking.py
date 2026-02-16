class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        self.last_offer = None
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        
        # If this is a counter-offer from partner
        if o is not None:
            # Calculate value of partner's offer to me
            offer_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Calculate how many turns remaining (including this acceptance)
            turns_remaining = total_turns - self.turn_count + 1
            
            # Acceptance threshold decreases as we get closer to deadline
            if turns_remaining <= 2:
                # Last 1-2 turns: accept anything positive
                if offer_value > 0:
                    return None
            elif turns_remaining <= 4:
                # Last 3-4 turns: accept if we get at least 30% of total value
                if offer_value >= self.total_value * 0.3:
                    return None
            else:
                # Early game: accept if we get at least 40% of total value
                if offer_value >= self.total_value * 0.4:
                    return None
        
        # Generate counter-offer
        # Calculate target value based on how many turns remaining
        turns_remaining = total_turns - self.turn_count
        if turns_remaining <= 0:
            target_value = self.total_value * 0.3
        elif turns_remaining <= 2:
            target_value = self.total_value * 0.4
        elif turns_remaining <= 6:
            target_value = self.total_value * 0.5
        else:
            target_value = self.total_value * 0.6
        
        # Create a reasonable counter-offer
        # Sort items by value to us (descending) to prioritize keeping high-value items
        item_indices = sorted(range(len(self.values)), key=lambda i: self.values[i], reverse=True)
        
        proposal = [0] * len(self.counts)
        current_value = 0
        
        # First, take all items with zero value (we don't care about them)
        for i in range(len(self.counts)):
            if self.values[i] == 0:
                proposal[i] = 0  # We don't need to claim worthless items
        
        # Then, greedily take valuable items until we reach our target
        for i in item_indices:
            if self.values[i] > 0:
                # Take as many as needed to reach target, but not more than available
                remaining_needed = target_value - current_value
                if remaining_needed <= 0:
                    break
                
                # How many of this item do we need to take?
                value_per_item = self.values[i]
                items_needed = min(self.counts[i], (remaining_needed + value_per_item - 1) // value_per_item)
                proposal[i] = items_needed
                current_value += items_needed * value_per_item
        
        # If we couldn't reach target (shouldn't happen with reasonable targets), take everything valuable
        if current_value < target_value:
            for i in range(len(self.counts)):
                if self.values[i] > 0:
                    proposal[i] = self.counts[i]
        
        # Ensure we don't request more than available
        for i in range(len(proposal)):
            proposal[i] = min(proposal[i], self.counts[i])
        
        # Special case: if this is our first move and we go first, be slightly more aggressive
        if self.turn_count == 1 and self.me == 0:
            # Take everything we value for the first offer
            proposal = []
            for i in range(len(self.counts)):
                if self.values[i] > 0:
                    proposal.append(self.counts[i])
                else:
                    proposal.append(0)
        
        return proposal