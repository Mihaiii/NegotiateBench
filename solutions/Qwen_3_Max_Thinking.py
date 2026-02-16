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
            # Record opponent's offer for analysis
            self.opponent_offers.append(o)
            
            # Calculate value of partner's offer to me
            offer_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Acceptance logic with time pressure
            if turns_remaining <= 1:
                # Last turn: accept anything positive
                if offer_value > 0:
                    return None
            elif turns_remaining <= 3:
                # Final rounds: accept if >= 25% of total
                if offer_value >= self.total_value * 0.25:
                    return None
            else:
                # Early/mid game: accept if >= 40% of total
                if offer_value >= self.total_value * 0.4:
                    return None
        
        # Generate counter-offer
        turns_elapsed = self.turn_count - (1 if o is None else 0)
        total_possible_turns = self.max_rounds * 2
        
        # Calculate concession factor (0 = most aggressive, 1 = most generous)
        if total_possible_turns > 0:
            concession_factor = min(1.0, turns_elapsed / total_possible_turns)
        else:
            concession_factor = 0.0
        
        # Determine our target share based on game stage
        if turns_remaining <= 2:
            target_share = 0.3  # Be more generous near deadline
        elif turns_remaining <= 6:
            target_share = 0.4
        else:
            target_share = 0.5 + (0.1 * (1 - concession_factor))  # Start ambitious, concede gradually
        
        target_value = self.total_value * target_share
        
        # Create proposal by prioritizing high-value items
        proposal = [0] * len(self.counts)
        current_value = 0
        
        # Sort items by our value (descending)
        item_indices = sorted(range(len(self.values)), key=lambda i: self.values[i], reverse=True)
        
        # Take valuable items greedily
        for i in item_indices:
            if self.values[i] > 0:
                # Calculate how many we can take while staying reasonable
                max_can_take = self.counts[i]
                
                # If we have opponent offers, infer what they might want
                if self.opponent_offers:
                    # Calculate what opponent seems to value (what they keep for themselves)
                    # Opponent's kept items = total - what they offered us
                    opponent_kept_avg = [0] * len(self.counts)
                    for offer in self.opponent_offers:
                        for j in range(len(self.counts)):
                            opponent_kept_avg[j] += (self.counts[j] - offer[j])
                    
                    for j in range(len(opponent_kept_avg)):
                        opponent_kept_avg[j] /= len(self.opponent_offers)
                    
                    # If opponent seems to value this item highly (keeps most of it), 
                    # we should be more willing to concede some
                    if opponent_kept_avg[i] > self.counts[i] * 0.7:
                        # They really want this item - take less
                        concession_on_item = min(1.0, concession_factor * 2)
                        max_can_take = int(max_can_take * (1 - concession_on_item * 0.5))
                
                # Take as many as needed for our target
                if current_value < target_value:
                    remaining_needed = target_value - current_value
                    items_needed = min(max_can_take, (remaining_needed + self.values[i] - 1) // self.values[i])
                    proposal[i] = int(items_needed)
                    current_value += items_needed * self.values[i]
                else:
                    proposal[i] = 0
        
        # Ensure all values are integers and within bounds
        for i in range(len(proposal)):
            proposal[i] = max(0, min(int(proposal[i]), self.counts[i]))
        
        # First move strategy: be ambitious but not greedy
        if self.turn_count == 1 and self.me == 0:
            # Take most of what we value, but leave something reasonable
            proposal = []
            for i in range(len(self.counts)):
                if self.values[i] > 0:
                    # Take 80-100% of valuable items on first move
                    take_amount = min(self.counts[i], max(1, int(self.counts[i] * 0.8)))
                    proposal.append(take_amount)
                else:
                    proposal.append(0)
        
        return proposal