class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        self.opponent_offers = []
        self.our_offers = []
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_remaining = total_turns - self.turn_count + 1
        
        # Handle opponent's offer
        if o is not None:
            # Validate offer
            valid = True
            offer_value = 0
            for i in range(len(o)):
                if o[i] < 0 or o[i] > self.counts[i]:
                    valid = False
                    break
                offer_value += o[i] * self.values[i]
            
            if not valid:
                return None
                
            self.opponent_offers.append(o)
            
            # Calculate minimum acceptable value based on time pressure and opponent behavior
            min_acceptable = self._calculate_min_acceptable(turns_remaining, offer_value)
            
            if offer_value >= min_acceptable:
                return None
        
        # Generate counter-offer
        return self._generate_counter_offer(o, turns_remaining)
    
    def _calculate_min_acceptable(self, turns_remaining: int, current_offer_value: float) -> float:
        """Calculate minimum value to accept based on time pressure and negotiation dynamics."""
        if turns_remaining == 1:
            return 1 if self.total_value > 0 else 0  # Accept any positive offer on last turn
        
        # Base thresholds that decrease over time
        if turns_remaining <= 2:
            base_threshold = 0.3
        elif turns_remaining <= 5:
            base_threshold = 0.4
        elif turns_remaining <= 10:
            base_threshold = 0.5
        else:
            base_threshold = 0.6
            
        # Adjust based on opponent behavior - if they're being reasonable, be more flexible
        if len(self.opponent_offers) >= 2:
            # Check if opponent is making concessions
            last_offer_val = sum(self.opponent_offers[-1][i] * self.values[i] for i in range(len(self.values)))
            prev_offer_val = sum(self.opponent_offers[-2][i] * self.values[i] for i in range(len(self.values)))
            
            # If opponent is offering us more, we can be slightly more flexible
            if last_offer_val > prev_offer_val:
                base_threshold *= 0.95
        
        return self.total_value * base_threshold
    
    def _generate_counter_offer(self, opponent_offer: list[int] | None, turns_remaining: int) -> list[int]:
        """Generate a counter-offer that balances our desires with likelihood of acceptance."""
        # Determine our target value based on time pressure
        if turns_remaining == 1:
            target_ratio = 0.3
        elif turns_remaining <= 3:
            target_ratio = 0.4
        elif turns_remaining <= 7:
            target_ratio = 0.5
        elif turns_remaining <= 12:
            target_ratio = 0.6
        else:
            target_ratio = 0.7
            
        target_value = self.total_value * target_ratio
        
        # If we have opponent offer history, use it to infer their preferences
        opponent_valuation_hints = self._infer_opponent_preferences()
        
        # Create initial proposal - take items we value most
        proposal = [0] * len(self.counts)
        current_value = 0
        
        # Sort items by our value (descending)
        valuable_items = [(self.values[i], i) for i in range(len(self.values))]
        valuable_items.sort(reverse=True)
        
        # First pass: take what we want
        for our_value, idx in valuable_items:
            if our_value == 0:
                continue
                
            if current_value >= target_value:
                break
                
            # How many can we take?
            max_available = self.counts[idx]
            
            # Calculate how many we need to reach target
            remaining_needed = target_value - current_value
            needed_items = (remaining_needed + our_value - 1) // our_value
            items_to_take = min(max_available, needed_items)
            
            # For first move, be slightly more generous
            if opponent_offer is None and len(self.opponent_offers) == 0:
                if max_available > 1:
                    items_to_take = min(items_to_take, max(1, max_available - 1))
            
            proposal[idx] = int(items_to_take)
            current_value += items_to_take * our_value
        
        # Second pass: adjust based on what opponent might accept
        # If we have info about what opponent values, try to give them more of those
        if opponent_valuation_hints and opponent_offer is not None:
            # Identify items opponent seems to value highly
            opponent_valuable_indices = []
            for idx, opp_hint_value in enumerate(opponent_valuation_hints):
                if opp_hint_value > 0 and self.values[idx] == 0:
                    # Opponent values it but we don't - definitely give it to them
                    proposal[idx] = 0
                elif opp_hint_value > 0 and self.values[idx] > 0:
                    # Both value it - consider sharing
                    if len(self.opponent_offers) > 0:
                        # See what opponent has been offering us for this item
                        avg_offered = sum(offer[idx] for offer in self.opponent_offers) / len(self.opponent_offers)
                        if avg_offered < self.counts[idx] * 0.3:  # Opponent keeps most of this
                            # Reduce what we take if we're being too greedy
                            if proposal[idx] > self.counts[idx] * 0.7:
                                proposal[idx] = max(0, int(self.counts[idx] * 0.5))
            
        # Ensure we don't exceed counts
        for i in range(len(proposal)):
            proposal[i] = max(0, min(proposal[i], self.counts[i]))
        
        # Special case: if this is late game and we're being stubborn, be more reasonable
        if turns_remaining <= 5 and len(self.our_offers) >= 2:
            # Check if we've been making the same offer repeatedly
            if len(self.our_offers) >= 2:
                last_our_offer = self.our_offers[-1]
                same_as_last = True
                for i in range(len(proposal)):
                    if proposal[i] != last_our_offer[i]:
                        same_as_last = False
                        break
                
                if same_as_last and turns_remaining <= 3:
                    # Make a small concession on something we care less about
                    for our_value, idx in sorted(valuable_items, reverse=False):  # Least valuable first
                        if our_value > 0 and proposal[idx] > 0:
                            proposal[idx] = max(0, proposal[idx] - 1)
                            break
        
        self.our_offers.append(proposal.copy())
        return proposal
    
    def _infer_opponent_preferences(self) -> list[float]:
        """Infer opponent's relative valuations based on their offers."""
        if not self.opponent_offers:
            return [0.0] * len(self.counts)
        
        # Calculate how much opponent keeps of each item (what they don't offer us)
        opponent_keeps = [0.0] * len(self.counts)
        
        for offer in self.opponent_offers:
            for i in range(len(self.counts)):
                kept = self.counts[i] - offer[i]
                opponent_keeps[i] += kept
        
        # Normalize to get relative preferences
        total_kept = sum(opponent_keeps)
        if total_kept == 0:
            return [1.0] * len(self.counts)
            
        return [kept / total_kept for kept in opponent_keeps]