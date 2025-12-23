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
        
        # If responding to an offer
        if o is not None:
            self.opponent_offers.append(o)
            offer_value = sum(o_i * v_i for o_i, v_i in zip(o, self.values))
            min_acceptable = self._min_acceptable_value()
            if offer_value >= min_acceptable:
                return None
        
        # Generate counter-offer
        return self._generate_offer()
    
    def _min_acceptable_value(self) -> int:
        total_turns = self.max_rounds * 2
        turns_remaining = total_turns - self.turn_count
        
        # If we're in the last possible turn to accept, accept anything > 0
        if turns_remaining <= 0:
            return 1
        
        # Calculate our target based on remaining time
        if self.turn_count == 1 and self.me == 0:
            # First move - be reasonable
            return max(1, (3 * self.total_value) // 5)
        elif turns_remaining <= 2:
            # Last chance to get a deal
            return max(1, self.total_value // 4)
        elif turns_remaining <= 4:
            return max(1, self.total_value // 3)
        elif turns_remaining <= 8:
            return max(1, self.total_value // 2)
        else:
            return max(1, (2 * self.total_value) // 3)
    
    def _generate_offer(self) -> list[int]:
        # Determine target value based on negotiation stage
        min_acceptable = self._min_acceptable_value()
        total_turns = self.max_rounds * 2
        turns_remaining = total_turns - self.turn_count
        
        if turns_remaining <= 0:
            target_value = self.total_value
        elif self.turn_count == 1 and self.me == 0:
            # First offer should be reasonable to start negotiation
            target_value = min(self.total_value, (3 * self.total_value) // 4)
        else:
            # Adjust target based on opponent behavior if we have data
            if self.opponent_offers:
                # Calculate average opponent generosity
                avg_opponent_value = 0
                for opp_offer in self.opponent_offers:
                    opp_value = sum(opp_offer[i] * self.values[i] for i in range(len(self.values)))
                    avg_opponent_value += opp_value
                avg_opponent_value //= len(self.opponent_offers)
                
                # If opponent is being generous, we can be more reasonable
                if avg_opponent_value > self.total_value // 2:
                    target_value = min(self.total_value, min_acceptable + (self.total_value - min_acceptable) // 4)
                else:
                    target_value = min(self.total_value, min_acceptable + (self.total_value - min_acceptable) // 2)
            else:
                target_value = min(self.total_value, min_acceptable + (self.total_value - min_acceptable) // 3)
        
        # Create list of items with their value and index
        valuable_items = []
        for i in range(len(self.counts)):
            if self.values[i] > 0:
                valuable_items.append((self.values[i], i))
        
        # Sort by value descending (highest value first)
        valuable_items.sort(reverse=True)
        
        # Start with taking nothing
        offer = [0] * len(self.counts)
        current_value = 0
        
        # Greedily add highest value items first
        for value, idx in valuable_items:
            if current_value >= target_value:
                break
            remaining_value_needed = target_value - current_value
            max_items_available = self.counts[idx]
            items_to_take = min(max_items_available, (remaining_value_needed + value - 1) // value)
            offer[idx] = items_to_take
            current_value += items_to_take * value
        
        # If we have opponent offer history, try to avoid items they seem to want
        if self.opponent_offers and valuable_items:
            # Infer what opponent values by seeing what they keep for themselves
            # Opponent keeps (counts[i] - our_offer[i]) for each item
            opponent_kept_analysis = [0] * len(self.counts)
            for opp_offer in self.opponent_offers:
                for i in range(len(self.counts)):
                    opponent_kept = self.counts[i] - opp_offer[i]
                    opponent_kept_analysis[i] += opponent_kept
            
            # Reduce our demand on items opponent seems to value highly
            # Only do this if we're not in the final rounds
            if turns_remaining > 2:
                for value, idx in valuable_items:
                    if offer[idx] > 0 and opponent_kept_analysis[idx] > 0:
                        # Opponent seems to want this item, consider reducing our ask
                        avg_kept = opponent_kept_analysis[idx] / len(self.opponent_offers)
                        if avg_kept >= self.counts[idx] * 0.7:  # Opponent keeps most of this item
                            # Reduce our demand by 1 if possible
                            if offer[idx] > 0 and current_value - value >= min_acceptable:
                                offer[idx] -= 1
                                current_value -= value
        
        # Ensure we don't exceed available counts (shouldn't happen but safety check)
        for i in range(len(offer)):
            offer[i] = min(offer[i], self.counts[i])
            
        return offer