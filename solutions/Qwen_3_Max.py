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
            
            # Accept offer if it meets our minimum threshold
            if offer_value >= self.total_value * 0.5:
                return None
            
            # In very late game, accept lower thresholds
            if turns_remaining <= 2 and offer_value >= self.total_value * 0.3:
                return None
            if turns_remaining == 0 and offer_value > 0:
                return None
        
        # Calculate minimum acceptable value based on remaining time
        if turns_remaining <= 2:
            min_value = self.total_value * 0.4
        elif turns_remaining <= 6:
            min_value = self.total_value * 0.5
        else:
            min_value = self.total_value * 0.6
        
        # Build offer by prioritizing high-value items
        offer = [0] * len(self.counts)
        current_value = 0
        
        # Create list of (value_per_item, index) and sort by value descending
        valuable_items = []
        for i in range(len(self.values)):
            if self.values[i] > 0:
                valuable_items.append((self.values[i], i))
        
        # Sort by value per item (descending)
        valuable_items.sort(reverse=True)
        
        # Take as many high-value items as needed to reach min_value
        for value_per_item, idx in valuable_items:
            if current_value >= min_value:
                break
            # Calculate how many of this item we need
            needed_value = min_value - current_value
            max_items = self.counts[idx]
            items_to_take = min(max_items, (needed_value + value_per_item - 1) // value_per_item)
            offer[idx] = int(items_to_take)
            current_value += offer[idx] * value_per_item
        
        # If we haven't reached min_value, take more items
        if current_value < min_value:
            for value_per_item, idx in valuable_items:
                while offer[idx] < self.counts[idx] and current_value < min_value:
                    offer[idx] += 1
                    current_value += value_per_item
        
        # Apply strategic concessions based on opponent behavior
        if self.opponent_offers:
            last_offer = self.opponent_offers[-1]
            # If opponent is consistently not offering us certain items,
            # and those items have low value to us, consider reducing our demand
            for i in range(len(self.values)):
                if self.values[i] > 0 and offer[i] > 0:
                    # If opponent never offers us this item (they keep it all)
                    if last_offer[i] == 0:
                        # Only concede if this item has relatively low value to us
                        if self.values[i] <= self.total_value / sum(self.counts):
                            offer[i] = max(0, offer[i] - 1)
                            break
        
        # Ensure offer is valid
        for i in range(len(offer)):
            offer[i] = max(0, min(offer[i], self.counts[i]))
        
        # Safety check: never offer nothing if we have valuable items
        if sum(offer[i] * self.values[i] for i in range(len(offer))) == 0:
            # Find the most valuable item and take at least one
            best_idx = max(range(len(self.values)), key=lambda i: self.values[i])
            if self.values[best_idx] > 0:
                offer[best_idx] = min(1, self.counts[best_idx])
        
        return offer