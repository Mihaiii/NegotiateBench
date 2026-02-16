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
            
            # Calculate minimum acceptable based on time pressure
            if turns_remaining == 1:
                # Last turn - accept anything positive
                if offer_value > 0:
                    return None
            elif turns_remaining <= 2:
                # Very last moments - accept if >= 20% of total
                if offer_value >= self.total_value * 0.2:
                    return None
            elif turns_remaining <= 4:
                # Near deadline - accept if >= 30% of total
                if offer_value >= self.total_value * 0.3:
                    return None
            elif turns_remaining <= 8:
                # Moderate pressure - accept if >= 40% of total
                if offer_value >= self.total_value * 0.4:
                    return None
            else:
                # Early game - be selective, accept if >= 50% of total
                if offer_value >= self.total_value * 0.5:
                    return None
        
        # Generate counter-offer
        proposal = [0] * len(self.counts)
        
        # If we have no history, start with ambitious offer
        if not self.opponent_offers and o is None:
            # First move: take everything valuable to us
            for i in range(len(self.counts)):
                if self.values[i] > 0:
                    proposal[i] = self.counts[i]
                else:
                    proposal[i] = 0
        elif not self.opponent_offers and o is not None:
            # First response: analyze what they offered us
            # They offered us 'o', so they want to keep (counts - o)
            # Take everything that's valuable to us, but be slightly more reasonable
            for i in range(len(self.counts)):
                if self.values[i] > 0:
                    # Take most of valuable items, but maybe leave a little
                    if self.counts[i] > 1:
                        proposal[i] = self.counts[i] - 1  # Leave 1 for them
                    else:
                        proposal[i] = self.counts[i]
                else:
                    proposal[i] = 0
        else:
            # We have history - analyze what they consistently reject
            # Find items where we might be overreaching
            opponent_wants = [0] * len(self.counts)
            my_last_offer = self.my_offers[-1] if self.my_offers else None
            
            # If we have a last offer and they rejected it, see what we took that they might want
            if my_last_offer is not None and len(self.opponent_offers) >= 1:
                # Their latest offer shows what they're willing to give us
                latest_opponent_offer = self.opponent_offers[-1]
                # Items we took in our last offer but they're not giving us in their offer
                # are likely valuable to them
                for i in range(len(self.counts)):
                    if my_last_offer[i] > latest_opponent_offer[i]:
                        # We're taking more than they're willing to give - they probably want this item
                        opponent_wants[i] = 1
            
            # Build proposal: prioritize items valuable to us, avoid items opponent seems to want
            item_indices = sorted(range(len(self.values)), key=lambda i: self.values[i], reverse=True)
            
            # Determine how generous to be based on time pressure
            if turns_remaining <= 2:
                generosity = 0.4  # Very generous near deadline
            elif turns_remaining <= 4:
                generosity = 0.3
            elif turns_remaining <= 8:
                generosity = 0.2
            else:
                generosity = 0.1  # Not very generous early on
            
            for i in item_indices:
                if self.values[i] <= 0:
                    proposal[i] = 0
                    continue
                
                # Base amount: take most of what's valuable to us
                base_take = self.counts[i]
                
                # If opponent seems to want this item, be more generous
                if opponent_wants[i]:
                    # Reduce our take based on time pressure
                    reduction = int(self.counts[i] * generosity)
                    proposal[i] = max(0, base_take - reduction)
                else:
                    # We can be more aggressive
                    proposal[i] = base_take
        
        # Ensure validity
        for i in range(len(proposal)):
            proposal[i] = max(0, min(proposal[i], self.counts[i]))
        
        self.my_offers.append(proposal.copy())
        return proposal