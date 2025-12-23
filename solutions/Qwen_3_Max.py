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
            
            # Calculate acceptance threshold based on round and opponent behavior
            total_turns = self.max_rounds * 2
            turns_elapsed = self.turn_count
            time_pressure = turns_elapsed / total_turns
            
            # Base acceptance threshold
            if time_pressure >= 0.8:  # Last 20% of turns
                min_acceptable = self.total_value * 0.4
            elif time_pressure >= 0.6:  # Last 40% of turns
                min_acceptable = self.total_value * 0.5
            elif time_pressure >= 0.4:  # Middle phase
                min_acceptable = self.total_value * 0.6
            else:  # Early phase
                min_acceptable = self.total_value * 0.65  # More reasonable early threshold
            
            # If opponent is being generous, accept reasonable offers
            if len(self.opponent_offers) >= 2:
                # Check if opponent is consistently offering good deals
                recent_offers = self.opponent_offers[-2:]
                avg_recent_value = sum(sum(offer[i] * self.values[i] for i in range(len(offer))) 
                                     for offer in recent_offers) / len(recent_offers)
                if avg_recent_value >= self.total_value * 0.55:
                    min_acceptable = min(min_acceptable, self.total_value * 0.55)
            
            if offer_value >= min_acceptable:
                return None
        
        # Generate counter-offer
        return self._generate_offer()
    
    def _generate_offer(self) -> list[int]:
        total_turns = self.max_rounds * 2
        turns_elapsed = self.turn_count
        time_pressure = turns_elapsed / total_turns
        
        # More reasonable target values
        if time_pressure >= 0.8:
            target_ratio = 0.65
        elif time_pressure >= 0.6:
            target_ratio = 0.7
        elif time_pressure >= 0.4:
            target_ratio = 0.75
        elif time_pressure >= 0.2:
            target_ratio = 0.8
        else:
            target_ratio = 0.85  # Still ambitious but not greedy
        
        target_value = self.total_value * target_ratio
        
        # Start with a reasonable base offer
        offer = [0] * len(self.counts)
        current_value = 0
        
        # Identify valuable items to us
        valuable_items = []
        for i in range(len(self.counts)):
            if self.values[i] > 0:
                valuable_items.append((self.values[i], i))
        valuable_items.sort(reverse=True)
        
        # Take high-value items first, but don't be greedy
        for value, idx in valuable_items:
            if current_value >= target_value:
                break
            # Calculate how many we actually need
            remaining_needed = target_value - current_value
            items_needed = min(self.counts[idx], int((remaining_needed + value - 1) // value))
            offer[idx] = items_needed
            current_value += items_needed * value
        
        # Adjust based on opponent behavior
        if self.opponent_offers:
            # Calculate what opponent typically keeps
            opponent_keeps = [0] * len(self.counts)
            for opp_offer in self.opponent_offers:
                for i in range(len(self.counts)):
                    opponent_keeps[i] += self.counts[i] - opp_offer[i]
            avg_opponent_keeps = [keeps / len(self.opponent_offers) for keeps in opponent_keeps]
            
            # Concede on items opponent clearly values more, especially if we're in middle/late game
            if turns_elapsed > 1:
                for i in range(len(self.counts)):
                    # If opponent keeps most of this item AND we don't value it highly relative to our best items
                    if (avg_opponent_keeps[i] >= self.counts[i] * 0.7 and 
                        self.values[i] < max(self.values) * 0.5):
                        # Reduce our demand significantly
                        offer[i] = max(0, offer[i] - 1)
                        if offer[i] < 0:
                            offer[i] = 0
        
        # Ensure we don't exceed available counts (safety check)
        for i in range(len(offer)):
            offer[i] = min(offer[i], self.counts[i])
            offer[i] = max(0, offer[i])
        
        # Last resort: if this is our final turn, make a very reasonable offer
        if self.turn_count >= total_turns - 1:
            # Aim for just over 50% to ensure acceptance
            target_value = self.total_value * 0.51
            offer = [0] * len(self.counts)
            current_value = 0
            
            valuable_items = [(self.values[i], i) for i in range(len(self.counts)) if self.values[i] > 0]
            valuable_items.sort(reverse=True)
            
            for value, idx in valuable_items:
                if current_value >= target_value:
                    break
                remaining_needed = target_value - current_value
                items_to_take = min(self.counts[idx], int((remaining_needed + value - 1) // value))
                offer[idx] = items_to_take
                current_value += items_to_take * value
        
        # Ensure offer is valid (non-negative, doesn't exceed counts)
        for i in range(len(offer)):
            if offer[i] < 0:
                offer[i] = 0
            if offer[i] > self.counts[i]:
                offer[i] = self.counts[i]
        
        return offer