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
            
            total_turns = self.max_rounds * 2
            turns_elapsed = self.turn_count
            time_pressure = turns_elapsed / total_turns
            
            # More reasonable acceptance thresholds
            if time_pressure >= 0.9:  # Very last turns
                min_acceptable = self.total_value * 0.4
            elif time_pressure >= 0.7:  # Late game
                min_acceptable = self.total_value * 0.45
            elif time_pressure >= 0.5:  # Middle game
                min_acceptable = self.total_value * 0.5
            else:  # Early game
                min_acceptable = self.total_value * 0.55
            
            # If opponent has been consistent and offering decent value, be more accepting
            if len(self.opponent_offers) >= 2:
                recent_values = []
                for offer in self.opponent_offers[-2:]:
                    val = sum(offer[i] * self.values[i] for i in range(len(offer)))
                    recent_values.append(val)
                avg_recent = sum(recent_values) / len(recent_values)
                if avg_recent >= self.total_value * 0.5:
                    min_acceptable = min(min_acceptable, self.total_value * 0.5)
            
            if offer_value >= min_acceptable:
                return None
        
        # Generate counter-offer
        return self._generate_offer()
    
    def _generate_offer(self) -> list[int]:
        total_turns = self.max_rounds * 2
        turns_elapsed = self.turn_count
        time_pressure = turns_elapsed / total_turns
        
        # More reasonable target ratios
        if time_pressure >= 0.8:
            target_ratio = 0.6
        elif time_pressure >= 0.6:
            target_ratio = 0.65
        elif time_pressure >= 0.3:
            target_ratio = 0.7
        else:
            target_ratio = 0.75  # Reasonable ambition early on
        
        target_value = self.total_value * target_ratio
        
        # Start with taking valuable items
        offer = [0] * len(self.counts)
        current_value = 0
        
        # Sort items by value to us (descending)
        valuable_items = [(self.values[i], i) for i in range(len(self.counts)) if self.values[i] > 0]
        valuable_items.sort(reverse=True)
        
        # Take what we need to reach target
        for value, idx in valuable_items:
            if current_value >= target_value:
                break
            remaining_needed = target_value - current_value
            items_needed = min(self.counts[idx], (remaining_needed + value - 1) // value)
            offer[idx] = int(items_needed)
            current_value += items_needed * value
        
        # Adjust based on opponent behavior - concede on items opponent clearly values
        if self.opponent_offers and turns_elapsed > 1:
            # Calculate what opponent typically keeps (what they don't offer us)
            opponent_keeps_total = [0] * len(self.counts)
            for opp_offer in self.opponent_offers:
                for i in range(len(self.counts)):
                    opponent_keeps_total[i] += self.counts[i] - opp_offer[i]
            
            avg_opponent_keeps = [keeps / len(self.opponent_offers) for keeps in opponent_keeps_total]
            
            # For items where opponent keeps most of them AND we don't value them highly
            for i in range(len(self.counts)):
                if (self.values[i] > 0 and 
                    avg_opponent_keeps[i] >= self.counts[i] * 0.6 and 
                    self.values[i] <= max(self.values) * 0.5):
                    # Reduce our demand on this item
                    offer[i] = max(0, offer[i] - 1)
        
        # Safety checks
        for i in range(len(offer)):
            offer[i] = min(offer[i], self.counts[i])
            offer[i] = max(0, offer[i])
        
        # Final turn - make a very reasonable offer (just over 50%)
        if self.turn_count >= total_turns - 1:
            target_value = self.total_value * 0.51
            offer = [0] * len(self.counts)
            current_value = 0
            
            valuable_items = [(self.values[i], i) for i in range(len(self.counts)) if self.values[i] > 0]
            valuable_items.sort(reverse=True)
            
            for value, idx in valuable_items:
                if current_value >= target_value:
                    break
                remaining_needed = target_value - current_value
                items_to_take = min(self.counts[idx], (remaining_needed + value - 1) // value)
                offer[idx] = int(items_to_take)
                current_value += items_to_take * value
        
        return offer