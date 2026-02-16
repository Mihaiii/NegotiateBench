class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        self.opponent_offers = []
        self.my_offers = []
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_remaining = total_turns - self.turn_count + 1
        
        # Handle opponent's offer
        if o is not None:
            self.opponent_offers.append(o)
            offer_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Calculate minimum acceptable based on time pressure and best alternative
            if turns_remaining == 1:
                # Last turn - accept anything positive
                if offer_value > 0:
                    return None
            elif turns_remaining <= 3:
                # Very last moments - accept if >= 25% of total
                if offer_value >= self.total_value * 0.25:
                    return None
            elif turns_remaining <= 6:
                # Near deadline - accept if >= 35% of total
                if offer_value >= self.total_value * 0.35:
                    return None
            elif turns_remaining <= 12:
                # Moderate pressure - accept if >= 45% of total
                if offer_value >= self.total_value * 0.45:
                    return None
            else:
                # Early game - be selective, accept if >= 55% of total
                if offer_value >= self.total_value * 0.55:
                    return None
        
        # Generate counter-offer
        proposal = [0] * len(self.counts)
        
        # Create list of items sorted by our value (descending)
        item_indices = sorted(range(len(self.values)), key=lambda i: self.values[i], reverse=True)
        
        # Determine concession level based on time pressure
        if turns_remaining <= 2:
            concession_factor = 0.5  # Very generous
        elif turns_remaining <= 4:
            concession_factor = 0.4
        elif turns_remaining <= 8:
            concession_factor = 0.3
        elif turns_remaining <= 16:
            concession_factor = 0.2
        else:
            concession_factor = 0.1  # Minimal concessions early on
        
        # If we have opponent offer history, use it to be more strategic
        if self.opponent_offers:
            # Get the opponent's most recent offer
            latest_opponent_offer = self.opponent_offers[-1]
            
            # For each item, determine how much we should take
            for i in item_indices:
                if self.values[i] <= 0:
                    proposal[i] = 0
                    continue
                
                # Base amount: we want all of it initially
                base_amount = self.counts[i]
                
                # If opponent has been consistently offering us less of this item,
                # they probably value it highly, so we should concede more
                opponent_offers_avg = sum(offer[i] for offer in self.opponent_offers) / len(self.opponent_offers)
                opponent_concession_ratio = opponent_offers_avg / self.counts[i] if self.counts[i] > 0 else 0
                
                # If opponent is offering us very little of this item (ratio < 0.3), 
                # they likely value it highly, so we should be more generous
                if opponent_concession_ratio < 0.3:
                    # They want this item - concede more
                    concession_amount = int(self.counts[i] * (concession_factor * 2))
                    proposal[i] = max(0, base_amount - concession_amount)
                elif opponent_concession_ratio < 0.6:
                    # Moderate concession
                    concession_amount = int(self.counts[i] * concession_factor)
                    proposal[i] = max(0, base_amount - concession_amount)
                else:
                    # They're willing to give us most of it - take aggressively
                    proposal[i] = base_amount
        else:
            # No history yet - start with aggressive but reasonable offer
            for i in item_indices:
                if self.values[i] <= 0:
                    proposal[i] = 0
                else:
                    # Take most items, but leave a small amount for items with high count
                    if self.counts[i] > 2:
                        proposal[i] = self.counts[i] - 1
                    else:
                        proposal[i] = self.counts[i]
        
        # Ensure validity
        for i in range(len(proposal)):
            proposal[i] = max(0, min(proposal[i], self.counts[i]))
        
        # Special case: if this is our first move and we're going first, be slightly more aggressive
        if o is None and len(self.my_offers) == 0:
            for i in range(len(self.counts)):
                if self.values[i] > 0:
                    proposal[i] = self.counts[i]
        
        self.my_offers.append(proposal.copy())
        return proposal