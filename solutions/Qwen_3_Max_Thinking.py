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
            # Validate opponent's offer
            valid_offer = True
            for i in range(len(o)):
                if o[i] < 0 or o[i] > self.counts[i]:
                    valid_offer = False
                    break
            if not valid_offer:
                return None  # Accept invalid offers as walking away
                
            self.opponent_offers.append(o)
            offer_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Calculate minimum acceptable value based on time pressure
            if turns_remaining == 1:
                # Last turn - accept anything positive
                if offer_value > 0:
                    return None
            elif turns_remaining <= 2:
                # Very close to deadline - accept if >= 20% of total
                if offer_value >= self.total_value * 0.2:
                    return None
            elif turns_remaining <= 4:
                # Close to deadline - accept if >= 30% of total
                if offer_value >= self.total_value * 0.3:
                    return None
            elif turns_remaining <= 8:
                # Moderate pressure - accept if >= 40% of total
                if offer_value >= self.total_value * 0.4:
                    return None
            else:
                # Early game - accept if >= 50% of total
                if offer_value >= self.total_value * 0.5:
                    return None
        
        # Generate counter-offer
        proposal = [0] * len(self.counts)
        
        # Calculate how much we should concede based on time pressure
        if turns_remaining <= 1:
            # Desperate - aim for 20% of total value
            target_value_ratio = 0.2
        elif turns_remaining <= 3:
            # Very generous - aim for 30% of total value
            target_value_ratio = 0.3
        elif turns_remaining <= 6:
            # Moderate concessions - aim for 40% of total value
            target_value_ratio = 0.4
        elif turns_remaining <= 12:
            # Some concessions - aim for 50% of total value
            target_value_ratio = 0.5
        else:
            # Aggressive - aim for 60% of total value
            target_value_ratio = 0.6
        
        target_value = self.total_value * target_value_ratio
        
        # Create list of items sorted by our value per item (descending)
        item_indices = sorted(range(len(self.values)), key=lambda i: self.values[i], reverse=True)
        
        # Greedily allocate items starting with highest value to us
        current_value = 0
        remaining_counts = self.counts.copy()
        
        for i in item_indices:
            if self.values[i] == 0:
                # We don't value this item, so take 0
                proposal[i] = 0
            else:
                # Determine how much to take
                remaining_value_needed = target_value - current_value
                if remaining_value_needed <= 0:
                    proposal[i] = 0
                else:
                    # Calculate maximum we can take
                    max_items = remaining_counts[i]
                    if max_items == 0:
                        proposal[i] = 0
                    else:
                        # Calculate how many items we need for remaining value
                        items_needed = min(max_items, (remaining_value_needed + self.values[i] - 1) // self.values[i])
                        
                        # Be more generous if we have opponent history
                        if self.opponent_offers and len(self.opponent_offers) >= 2:
                            # Look at recent opponent behavior
                            recent_offers = self.opponent_offers[-2:]
                            avg_opponent_take = sum(offer[i] for offer in recent_offers) / len(recent_offers)
                            # If opponent is consistently taking more of this item, they probably value it
                            # So we should be more generous (take less)
                            if avg_opponent_take > self.counts[i] * 0.7:
                                # They really want this - take only what we absolutely need
                                items_to_take = min(items_needed, max(1, max_items // 3))
                            elif avg_opponent_take > self.counts[i] * 0.4:
                                # They somewhat want this - take moderately
                                items_to_take = min(items_needed, max(1, max_items // 2))
                            else:
                                # They don't mind giving this up - take what we need
                                items_to_take = items_needed
                        else:
                            # No history or early game - be reasonable
                            if turns_remaining > 10:
                                # Early game - be more aggressive
                                items_to_take = min(items_needed, max_items)
                            else:
                                # Later game - leave some room
                                items_to_take = min(items_needed, max(1, max_items - 1))
                        
                        proposal[i] = int(items_to_take)
                        current_value += proposal[i] * self.values[i]
                        remaining_counts[i] -= proposal[i]
        
        # Ensure we don't exceed counts and all values are integers
        for i in range(len(proposal)):
            proposal[i] = max(0, min(int(proposal[i]), self.counts[i]))
        
        # Special case: if this is our first move, ensure we don't take everything
        if o is None and len(self.opponent_offers) == 0:
            # Make a reasonable first offer - don't be too greedy
            for i in range(len(self.counts)):
                if self.values[i] > 0:
                    if self.counts[i] > 1:
                        # Leave at least 1 item of each valuable type
                        proposal[i] = min(proposal[i], self.counts[i] - 1)
                    else:
                        proposal[i] = self.counts[i]
        
        # Sanity check: ensure total doesn't exceed counts
        for i in range(len(proposal)):
            if proposal[i] > self.counts[i]:
                proposal[i] = self.counts[i]
        
        return proposal