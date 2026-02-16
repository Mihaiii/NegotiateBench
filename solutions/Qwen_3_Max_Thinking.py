class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        self.opponent_offers = []
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_elapsed = self.turn_count - (1 if o is None else 0)
        turns_remaining = total_turns - self.turn_count + 1
        
        # Handle opponent's offer
        if o is not None:
            self.opponent_offers.append(o)
            offer_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Accept if it meets our minimum threshold
            if turns_remaining <= 1:
                # Last turn: accept anything positive
                if offer_value > 0:
                    return None
            elif turns_remaining <= 4:
                # Near deadline: accept if >= 30% of total
                if offer_value >= self.total_value * 0.3:
                    return None
            elif turns_remaining <= 8:
                # Mid-game: accept if >= 40% of total
                if offer_value >= self.total_value * 0.4:
                    return None
            else:
                # Early game: accept if >= 50% of total
                if offer_value >= self.total_value * 0.5:
                    return None
        
        # Generate counter-offer: prioritize items by our value
        # Calculate how much we should concede based on time pressure
        if total_turns > 0:
            time_pressure = min(1.0, turns_elapsed / total_turns)
        else:
            time_pressure = 0.0
        
        # Target value decreases as time runs out
        if turns_remaining <= 2:
            target_ratio = 0.35  # Be generous near deadline
        elif turns_remaining <= 6:
            target_ratio = 0.45
        elif turns_remaining <= 12:
            target_ratio = 0.55
        else:
            target_ratio = 0.65  # Start ambitious
        
        target_value = self.total_value * target_ratio
        
        # Create proposal by taking valuable items first
        proposal = [0] * len(self.counts)
        current_value = 0
        
        # Sort items by value (descending) to prioritize what we want most
        item_indices = sorted(range(len(self.values)), key=lambda i: self.values[i], reverse=True)
        
        for i in item_indices:
            if self.values[i] <= 0:
                continue
                
            # How many of this item can we take?
            remaining_count = self.counts[i]
            
            # If we have opponent offers, see what they typically keep for themselves
            if self.opponent_offers:
                # Calculate average amount opponent keeps (total - what they offer us)
                opponent_keeps_avg = 0
                for offer in self.opponent_offers:
                    opponent_keeps_avg += (self.counts[i] - offer[i])
                opponent_keeps_avg /= len(self.opponent_offers)
                
                # If opponent consistently keeps most of this item, be more willing to concede
                if opponent_keeps_avg > self.counts[i] * 0.6:
                    # They value this item highly - take less aggressively
                    concession_factor = min(0.7, time_pressure * 0.8)
                    max_take = int(remaining_count * (1 - concession_factor))
                else:
                    max_take = remaining_count
            else:
                max_take = remaining_count
            
            # Take what we need to reach our target
            if current_value < target_value and max_take > 0:
                value_needed = target_value - current_value
                items_needed = min(max_take, (value_needed + self.values[i] - 1) // self.values[i])
                proposal[i] = int(items_needed)
                current_value += items_needed * self.values[i]
            else:
                proposal[i] = 0
        
        # Ensure all values are valid
        for i in range(len(proposal)):
            if proposal[i] < 0:
                proposal[i] = 0
            elif proposal[i] > self.counts[i]:
                proposal[i] = self.counts[i]
        
        # First move: be ambitious but reasonable
        if self.turn_count == 1 and self.me == 0:
            proposal = []
            for i in range(len(self.counts)):
                if self.values[i] > 0:
                    # Take 80-100% of valuable items
                    take_amount = min(self.counts[i], max(1, int(self.counts[i] * 0.8)))
                    proposal.append(take_amount)
                else:
                    proposal.append(0)
        
        return proposal