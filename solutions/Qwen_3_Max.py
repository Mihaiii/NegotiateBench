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
        turns_remaining = total_turns - self.turn_count
        
        # Handle incoming offer
        if o is not None:
            self.opponent_offers.append(o)
            offer_value = sum(o_i * v_i for o_i, v_i in zip(o, self.values))
            
            # Acceptance thresholds based on negotiation stage
            if turns_remaining == 0:
                # Last chance - accept anything > 0
                if offer_value > 0:
                    return None
            elif turns_remaining <= 2:
                # Very late game - accept 40% or more
                if offer_value >= self.total_value * 0.4:
                    return None
            elif turns_remaining <= 4:
                # Late game - accept 50% or more  
                if offer_value >= self.total_value * 0.5:
                    return None
            elif turns_remaining <= 8:
                # Mid game - accept 60% or more
                if offer_value >= self.total_value * 0.6:
                    return None
            else:
                # Early game - accept 70% or more
                if offer_value >= self.total_value * 0.7:
                    return None
        
        # Calculate target share based on how much time is left
        # More aggressive early, more generous late
        progress = self.turn_count / total_turns
        if progress < 0.25:
            target_share = 0.75  # Very aggressive early
        elif progress < 0.5:
            target_share = 0.65  # Still aggressive
        elif progress < 0.75:
            target_share = 0.55  # Moderate
        else:
            target_share = 0.45  # Generous in late game
        
        target_value = self.total_value * target_share
        
        # Create base offer by taking highest value items first
        offer = [0] * len(self.counts)
        current_value = 0
        
        # Sort items by our value per item (descending)
        item_indices = sorted(range(len(self.values)), key=lambda i: self.values[i], reverse=True)
        
        for i in item_indices:
            if self.values[i] == 0:
                continue
            if current_value >= target_value:
                break
            needed_value = target_value - current_value
            items_needed = min(self.counts[i], (needed_value + self.values[i] - 1) // self.values[i])
            offer[i] = int(items_needed)
            current_value += offer[i] * self.values[i]
        
        # Apply strategic concessions based on opponent's recent behavior
        if self.opponent_offers:
            last_opponent_offer = self.opponent_offers[-1]
            # The opponent is keeping (counts[i] - last_opponent_offer[i]) for themselves
            # We should be more willing to concede items where opponent is demanding a lot
            
            # Calculate how much opponent wants each item (what they're NOT offering us)
            opponent_demands = [self.counts[i] - last_opponent_offer[i] for i in range(len(self.counts))]
            
            # Make additional concessions on items that opponent highly demands
            # but that have lower value to us
            concession_items = []
            for i in range(len(self.values)):
                if opponent_demands[i] > 0 and offer[i] > 0:
                    # Priority: high opponent demand + low our value
                    priority = opponent_demands[i] * (1.0 / (self.values[i] + 1))  # Avoid division by zero
                    concession_items.append((priority, i))
            
            # Sort by priority (highest priority first)
            concession_items.sort(reverse=True)
            
            # Make one strategic concession if we're not being too generous already
            if current_value > target_value * 0.8 and concession_items:
                for _, item_idx in concession_items[:2]:  # Try top 2 items
                    if offer[item_idx] > 0:
                        offer[item_idx] = max(0, offer[item_idx] - 1)
                        break
        
        # Ensure offer is valid
        for i in range(len(offer)):
            offer[i] = min(offer[i], self.counts[i])
            offer[i] = max(0, offer[i])
        
        # Safety check: if we're asking for nothing, take at least one valuable item
        if sum(offer) == 0:
            best_item = max(range(len(self.values)), key=lambda i: self.values[i])
            offer[best_item] = min(1, self.counts[best_item])
        
        return offer