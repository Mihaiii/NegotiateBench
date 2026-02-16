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
        turns_remaining = total_turns - self.turn_count + 1
        
        # Handle opponent's offer
        if o is not None:
            self.opponent_offers.append(o)
            offer_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Acceptance logic based on time pressure
            if turns_remaining == 1:
                # Last possible turn - accept anything positive
                if offer_value > 0:
                    return None
            elif turns_remaining <= 3:
                # Very late game - accept if >= 25% of total
                if offer_value >= self.total_value * 0.25:
                    return None
            elif turns_remaining <= 6:
                # Late game - accept if >= 35% of total  
                if offer_value >= self.total_value * 0.35:
                    return None
            elif turns_remaining <= 12:
                # Mid game - accept if >= 45% of total
                if offer_value >= self.total_value * 0.45:
                    return None
            else:
                # Early game - accept if >= 55% of total
                if offer_value >= self.total_value * 0.55:
                    return None
        
        # Generate counter-offer
        # Calculate target value based on time pressure
        if turns_remaining <= 2:
            target_ratio = 0.4  # Be generous near deadline
        elif turns_remaining <= 6:
            target_ratio = 0.5
        elif turns_remaining <= 12:
            target_ratio = 0.6
        else:
            target_ratio = 0.7  # Start ambitious
        
        target_value = self.total_value * target_ratio
        
        # Create proposal by taking valuable items first
        proposal = [0] * len(self.counts)
        current_value = 0
        
        # Sort items by our value (descending)
        item_indices = sorted(range(len(self.values)), key=lambda i: self.values[i], reverse=True)
        
        # If we have opponent offers, adjust based on what they keep
        opponent_patterns = {}
        if self.opponent_offers:
            for i in range(len(self.counts)):
                # Calculate how much opponent typically keeps for themselves
                # (total - what they offer us)
                avg_opponent_keeps = sum(self.counts[i] - offer[i] for offer in self.opponent_offers) / len(self.opponent_offers)
                opponent_patterns[i] = avg_opponent_keeps / self.counts[i] if self.counts[i] > 0 else 0
        
        for i in item_indices:
            if self.values[i] <= 0:
                continue
                
            # Determine how much we can reasonably take
            max_available = self.counts[i]
            
            # If opponent consistently keeps most of this item, be more willing to concede
            if i in opponent_patterns and opponent_patterns[i] > 0.7:
                # They really want this item - take less
                max_take = max(0, int(max_available * 0.3))
            elif i in opponent_patterns and opponent_patterns[i] > 0.5:
                # They somewhat want this - take moderately
                max_take = max(0, int(max_available * 0.5))
            else:
                # They don't seem to care - take more
                max_take = max_available
            
            # Take what we need to reach target
            if current_value < target_value and max_take > 0:
                value_needed = target_value - current_value
                items_needed = min(max_take, (value_needed + self.values[i] - 1) // self.values[i])
                proposal[i] = int(items_needed)
                current_value += items_needed * self.values[i]
        
        # Handle first move specially - be ambitious but not greedy
        if self.turn_count == 1 and o is None:
            proposal = []
            for i in range(len(self.counts)):
                if self.values[i] > 0:
                    # Take 80-100% of valuable items, but not necessarily all
                    take_ratio = 0.8 if self.counts[i] > 1 else 1.0
                    take_amount = min(self.counts[i], max(1, int(self.counts[i] * take_ratio)))
                    proposal.append(take_amount)
                else:
                    proposal.append(0)
        
        # Ensure validity
        for i in range(len(proposal)):
            proposal[i] = max(0, min(proposal[i], self.counts[i]))
        
        return proposal