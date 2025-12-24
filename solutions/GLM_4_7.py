class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.num_types = len(counts)
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Negotiation state
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.turn = 0
        
        # Opponent modeling
        # We assume initially the opponent values items similarly to us (neutral prior)
        self.opp_values = list(values)
        
        # Track what we are currently demanding.
        # We initialize our demand to be everything that has value to us.
        self.my_demands = [c if v > 0 else 0 for c, v in zip(counts, values)]

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn += 1
        
        # 1. Analyze Opponent's Offer (if any) and Update Estimates
        if o is not None:
            self._update_opponent_model(o)
            
            offer_value_to_me = sum(self.values[i] * o[i] for i in range(self.num_types))
            
            # Acceptance Strategy
            # We accept if the value is high enough. 
            # As we run out of turns, we lower our standards.
            # We calculate a dynamic threshold.
            
            # Calculate value of what we would keep if we accepted
            # (which is simply the value of o, since o is what is offered TO us)
            current_val = offer_value_to_me
            
            # Minimum acceptable value drops as turns progress
            # Start at ~75% of total, drop to 0% at the very end
            progress = self.turn / self.total_turns
            threshold = self.total_value * (1.0 - progress * 0.8)
            
            # If it's the very last turn, accept anything positive to avoid 0
            if self.turn >= self.total_turns:
                if current_val > 0:
                    return None
            
            # Accept if it meets the threshold
            if current_val >= threshold:
                return None

        # 2. Generate Counter-Offer
        return self._generate_counter_offer()

    def _update_opponent_model(self, offer_to_me: list[int]):
        """
        Updates our estimate of the opponent's values based on their offer.
        offer_to_me: list of items the opponent gives to us.
        The opponent keeps: self.counts[i] - offer_to_me[i]
        """
        learning_rate = 1.0
        
        # Items the opponent keeps are likely valuable to them
        # Items the opponent offers to us are likely less valuable
        for i in range(self.num_types):
            keep_count = self.counts[i] - offer_to_me[i]
            give_count = offer_to_me[i]
            
            # Simple heuristic:
            # If they keep it, we assume they value it more than we thought
            # If they give it, we assume they value it less
            self.opp_values[i] += keep_count * learning_rate
            self.opp_values[i] -= give_count * learning_rate
            
            # Ensure non-negative
            if self.opp_values[i] < 0:
                self.opp_values[i] = 0

        # Normalize estimates so total value matches the known total value
        # This is a constraint from the problem description.
        current_est_total = sum(self.opp_values[i] * self.counts[i] for i in range(self.num_types))
        if current_est_total > 0:
            factor = self.total_value / current_est_total
            for i in range(self.num_types):
                self.opp_values[i] = int(self.opp_values[i] * factor)
                
    def _generate_counter_offer(self) -> list[int]:
        """
        Generates an offer by conceding items that are:
        1. High value to the opponent (relative to their other options)
        2. Low value to us (relative to our other options)
        """
        
        # If this is the very last offer we can make before the game ends,
        # we need to be very generous to ensure acceptance.
        if self.turn >= self.total_turns - 1:
            # Offer a "fair" split based on estimated values
            return self._generate_fair_split()
            
        # Find the best item to concede.
        # We want to give up an item we are currently demanding.
        # Score = Estimated Opponent Value / My Value.
        # Higher score means the opponent values it relatively more than I do.
        
        best_idx = -1
        best_ratio = -1.0
        
        for i in range(self.num_types):
            # Can only concede items we currently have in our demand
            if self.my_demands[i] > 0:
                my_val = self.values[i]
                opp_val = self.opp_values[i]
                
                # Avoid division by zero
                if my_val == 0:
                    # If I value it 0, I should have already conceded it in init,
                    # but if it's still here, concede it immediately.
                    ratio = float('inf')
                else:
                    ratio = opp_val / my_val
                
                if ratio > best_ratio:
                    best_ratio = ratio
                    best_idx = i
        
        # Concede the selected item
        if best_idx != -1:
            # We concede the entire type of item to make progress clear
            self.my_demands[best_idx] = 0
        else:
            # If we can't find a best item (e.g. we have nothing left), 
            # we probably already accepted or conceded everything.
            # Fallback: Return current demands.
            pass
            
        return self.my_demands

    def _generate_fair_split(self) -> list[int]:
        """
        Creates a split aiming for approximately 50% of the total value
        based on our estimates of the opponent's values.
        """
        offer = self.counts.copy()
        
        # We want to give the opponent items worth ~50% of total.
        # Start by giving them everything.
        # Then take items back that are most valuable to US and least valuable to THEM.
        
        # 1. Identify all items
        item_indices = list(range(self.num_types))
        
        # 2. Sort items by efficiency (My Value / Opponent Value) descending
        # We want to keep items with High My Value and Low Opponent Value.
        def efficiency(i):
            if self.opp_values[i] == 0: return float('inf')
            return self.values[i] / self.opp_values[i]
            
        item_indices.sort(key=efficiency, reverse=True)
        
        current_my_value = 0
        target_my_value = self.total_value / 2.0
        
        # 3. Take items back until we reach our target
        for i in item_indices:
            if current_my_value >= target_my_value:
                # Give the rest to opponent (set to 0)
                offer[i] = 0
            else:
                # Take this item for myself (set to count)
                offer[i] = self.counts[i]
                current_my_value += self.values[i] * self.counts[i]
                
        return offer