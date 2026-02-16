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
            
            # Calculate minimum acceptable value based on time pressure
            if turns_remaining == 1:
                # Last turn - accept anything positive
                if offer_value > 0:
                    return None
            elif turns_remaining <= 4:
                # Very close to deadline - accept if >= 30% of total
                if offer_cost >= self.total_value * 0.3:
                    return None
            elif turns_remaining <= 8:
                # Moderate pressure - accept if >= 40% of total
                if offer_value >= self.total_value * 0.4:
                    return None
            else:
                # Early game - accept if >= 50% of total
                if offer_value >= self.total_value * 0.5:
                    return None
        
        # Generate counter-offer - start with what we want most
        proposal = [0] * len(self.counts)
        
        # Create list of items sorted by our value per item (descending)
        item_indices = sorted(range(len(self.values)), key=lambda i: self.values[i], reverse=True)
        
        # Calculate how much we should concede based on time pressure
        if turns_remaining <= 2:
            # Very generous - aim for 40% of total value
            target_value_ratio = 0.4
        elif turns_remaining <= 6:
            # Moderate concessions - aim for 50% of total value
            target_value_ratio = 0.5
        elif turns_remaining <= 12:
            # Some concessions - aim for 60% of total value
            target_value_ratio = 0.6
        else:
            # Aggressive - aim for 70% of total value
            target_value_ratio = 0.7
        
        target_value = self.total_value * target_value_ratio
        
        # Greedily allocate items starting with highest value to us
        current_value = 0
        for i in item_indices:
            if self.values[i] == 0:
                # We don't value this item, so take 0
                proposal[i] = 0
            else:
                # Take as much as we can while staying near our target
                # But be reasonable - don't take everything if we have history
                if self.opponent_offers:
                    # Look at opponent's recent offers to see what they might accept
                    recent_opponent_offer = self.opponent_offers[-1]
                    # If opponent is offering us less of this item, they probably value it
                    # So we should be more generous and take less
                    if recent_opponent_offer[i] < self.counts[i] * 0.5:
                        # They want this item - take only what we need for our target
                        max_take = min(self.counts[i], max(1, self.counts[i] // 2))
                        # Calculate how much we can take without exceeding target
                        remaining_value_needed = target_value - current_value
                        if remaining_value_needed > 0:
                            items_needed = min(max_take, (remaining_value_needed + self.values[i] - 1) // self.values[i])
                            proposal[i] = max(0, min(items_needed, max_take))
                        else:
                            proposal[i] = 0
                    else:
                        # They're willing to give us this item - take more
                        remaining_value_needed = target_value - current_value
                        if remaining_value_needed > 0:
                            items_needed = min(self.counts[i], (remaining_value_needed + self.values[i] - 1) // self.values[i])
                            proposal[i] = items_needed
                        else:
                            proposal[i] = 0
                else:
                    # No history - be aggressive but reasonable
                    remaining_value_needed = target_value - current_value
                    if remaining_value_needed > 0:
                        items_needed = min(self.counts[i], (remaining_value_needed + self.values[i] - 1) // self.values[i])
                        # Always leave at least 1 item if count > 1 to show willingness to negotiate
                        if self.counts[i] > 1:
                            proposal[i] = min(items_needed, self.counts[i] - 1)
                        else:
                            proposal[i] = items_needed
                    else:
                        proposal[i] = 0
                
                current_value += proposal[i] * self.values[i]
        
        # Ensure we don't exceed counts
        for i in range(len(proposal)):
            proposal[i] = max(0, min(proposal[i], self.counts[i]))
        
        # Special case: if this is our first move, be slightly more aggressive
        if o is None and len(self.opponent_offers) == 0:
            for i in range(len(self.counts)):
                if self.values[i] > 0:
                    # Take all valuable items, but leave some room for negotiation
                    if self.counts[i] > 2:
                        proposal[i] = self.counts[i] - 1
                    else:
                        proposal[i] = self.counts[i]
        
        return proposal