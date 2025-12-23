class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        self.me = me
        self.offer_history = []
        self.their_offer_history = []
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_left = total_turns - self.turn_count + 1
        
        if o is not None:
            self.their_offer_history.append(o)
            my_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            if self._should_accept(my_value, turns_left):
                return None
        
        new_offer = self._make_offer(turns_left)
        self.offer_history.append(new_offer)
        return new_offer
    
    def _should_accept(self, offered_value: int, turns_left: int) -> bool:
        """Decide whether to accept an offer based on value and game state."""
        if turns_left <= 1:
            return offered_value > 0
        
        # Calculate acceptance threshold based on remaining turns
        progress = 1 - (turns_left / (self.max_rounds * 2))
        
        # Start at 60% and gradually decrease to 20%
        base_threshold = 0.60 - (progress * 0.40)
        
        # Accept anything decent in the final turns
        if turns_left <= 2:
            return offered_value >= self.total_value * 0.20
        elif turns_left <= 4:
            return offered_value >= self.total_value * 0.35
        
        # Check if opponent is making steady concessions
        if len(self.their_offer_history) >= 2:
            prev_value = sum(self.their_offer_history[-2][i] * self.values[i] 
                           for i in range(len(self.values)))
            
            # If they're improving their offer, be more willing to accept
            if offered_value > prev_value and offered_value >= self.total_value * (base_threshold - 0.10):
                return True
        
        # If we're in a deadlock (both sides stubborn), accept reasonable offers
        if len(self.their_offer_history) >= 5:
            recent_values = [sum(self.their_offer_history[i][j] * self.values[j] 
                               for j in range(len(self.values))) 
                           for i in range(-5, 0)]
            
            # Check for stable offers (opponent not budging)
            if max(recent_values) - min(recent_values) <= self.total_value * 0.05:
                best_offered = max(recent_values)
                # If it's the best they'll give and time is running out
                if offered_value >= best_offered * 0.95 and turns_left <= self.max_rounds:
                    if offered_value >= self.total_value * 0.30:
                        return True
        
        return offered_value >= self.total_value * base_threshold
    
    def _make_offer(self, turns_left: int) -> list[int]:
        """Generate a strategic counter-offer."""
        progress = 1 - (turns_left / (self.max_rounds * 2))
        
        # Start aggressive, gradually concede
        if turns_left <= 2:
            target_ratio = 0.40
        elif turns_left <= 4:
            target_ratio = 0.50
        elif turns_left <= 8:
            target_ratio = 0.55
        else:
            # Early game: be aggressive but not unreasonable
            target_ratio = 0.65 - (progress * 0.10)
        
        # Adapt based on opponent behavior
        if len(self.their_offer_history) >= 3:
            recent = self.their_offer_history[-3:]
            their_values = [sum(o[i] * self.values[i] for i in range(len(o))) for o in recent]
            
            # If opponent is stubborn and making reasonable offers
            if max(their_values) - min(their_values) <= self.total_value * 0.05:
                best_they_offered = max(their_values)
                # Make gradual concessions to break deadlock
                if best_they_offered >= self.total_value * 0.30 and turns_left <= 12:
                    target_ratio = min(target_ratio, 0.55)
        
        target_value = target_ratio * self.total_value
        
        # Build offer by prioritizing high-value items
        items = []
        for i in range(len(self.counts)):
            if self.values[i] > 0:
                # Value per item for sorting
                items.append((self.values[i], i))
        
        items.sort(reverse=True)
        
        # Greedy allocation
        offer = [0] * len(self.counts)
        current_value = 0
        
        for val, idx in items:
            # Take items until we reach target
            for _ in range(self.counts[idx]):
                if current_value >= target_value:
                    break
                offer[idx] += 1
                current_value += val
        
        # Make small concessions over time if we keep offering the same thing
        if len(self.offer_history) >= 3:
            last_offers = self.offer_history[-3:]
            if all(o == last_offers[0] for o in last_offers):
                # We've been stubborn, make a concession
                for i in range(len(offer)):
                    if offer[i] > 0 and self.values[i] > 0:
                        # Give up one item of lowest non-zero value we're keeping
                        min_val_idx = min(
                            [j for j in range(len(offer)) if offer[j] > 0 and self.values[j] > 0],
                            key=lambda j: self.values[j]
                        )
                        if offer[min_val_idx] > 0:
                            offer[min_val_idx] -= 1
                            break
        
        return offer