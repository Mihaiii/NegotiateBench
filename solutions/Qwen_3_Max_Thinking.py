class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.turn_count = 0
        self.best_offer_value = -1
        self.opponent_offers = []
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        total_turns = self.max_rounds * 2
        turns_remaining = total_turns - self.turn_count + 1
        
        # Handle opponent's offer
        if o is not None:
            # Validate offer
            offer_value = 0
            valid = True
            for i in range(len(o)):
                if o[i] < 0 or o[i] > self.counts[i]:
                    valid = False
                    break
                offer_value += o[i] * self.values[i]
            
            if not valid:
                return None
                
            self.opponent_offers.append(o)
            self.best_offer_value = max(self.best_offer_value, offer_value)
            
            # Acceptance logic
            if turns_remaining == 1:
                # Last turn - accept anything better than nothing
                if offer_value > 0:
                    return None
            else:
                # Calculate minimum acceptable based on time pressure
                # Early rounds: be picky (want 70-80% of total)
                # Late rounds: be flexible (accept 30-50% of total)
                progress = (self.turn_count - 1) / total_turns
                min_ratio = 0.3 + (0.5 * (1 - progress))  # Start at 80%, end at 30%
                min_acceptable = self.total_value * min_ratio
                
                # Also accept if it's the best we've seen and we're getting close to deadline
                if offer_value >= min_acceptable or (offer_value == self.best_offer_value and turns_remaining <= 3):
                    return None
        
        # Generate counter-offer
        return self._generate_offer(turns_remaining, total_turns)
    
    def _generate_offer(self, turns_remaining: int, total_turns: int) -> list[int]:
        # Determine how aggressive to be based on turn number
        progress = (total_turns - turns_remaining + 1) / total_turns
        target_ratio = 0.8 - 0.5 * progress  # Start at 80%, end at 30%
        target_value = self.total_value * target_ratio
        
        # Start with taking all items we value
        proposal = self.counts.copy()
        
        # Don't take items we don't value (unless opponent also doesn't seem to value them)
        for i in range(len(self.counts)):
            if self.values[i] == 0:
                # If we have opponent offer history, see what they kept
                if self.opponent_offers:
                    # What opponent kept in their offers (on average)
                    avg_kept = 0
                    for offer in self.opponent_offers:
                        kept = self.counts[i] - offer[i]
                        avg_kept += kept
                    avg_kept /= len(self.opponent_offers)
                    # If opponent consistently keeps this item, let them have it
                    if avg_kept > 0.5 * self.counts[i]:
                        proposal[i] = 0
                else:
                    # No history - assume opponent might value it, so don't take it
                    proposal[i] = 0
        
        # Calculate current value of proposal
        current_value = sum(proposal[i] * self.values[i] for i in range(len(self.counts)))
        
        # If we're over target, consider giving up some items we value less
        if current_value > target_value and self.opponent_offers:
            # Sort items by our value per item (lowest first among items we value)
            item_priority = []
            for i in range(len(self.counts)):
                if self.values[i] > 0 and proposal[i] > 0:
                    item_priority.append((self.values[i], i))
            item_priority.sort()  # Lowest value items first
            
            # Also consider what opponent seems to want to keep
            for _, i in item_priority:
                if current_value <= target_value * 1.1:
                    break
                    
                # Check if opponent seems to value this item highly
                if self.opponent_offers:
                    avg_kept = sum(self.counts[i] - offer[i] for offer in self.opponent_offers) / len(self.opponent_offers)
                    keep_ratio = avg_kept / self.counts[i] if self.counts[i] > 0 else 0
                    
                    # If opponent keeps most of this item, consider giving some up
                    if keep_ratio > 0.7 and proposal[i] > 0:
                        # Give up one unit at a time
                        proposal[i] = max(0, proposal[i] - 1)
                        current_value = sum(proposal[j] * self.values[j] for j in range(len(self.counts)))
        
        # Handle edge case: if we're first and this is turn 1, be slightly more generous
        if self.turn_count == 1 and self.me == 0:
            # Reduce target slightly for first offer
            current_value = sum(proposal[i] * self.values[i] for i in range(len(self.counts)))
            target_value_first = self.total_value * 0.7
            if current_value > target_value_first:
                # Give up lowest value items first
                item_priority = []
                for i in range(len(self.counts)):
                    if self.values[i] > 0 and proposal[i] > 0:
                        item_priority.append((self.values[i], i))
                item_priority.sort()
                for _, i in item_priority:
                    if current_value <= target_value_first:
                        break
                    if proposal[i] > 0:
                        proposal[i] -= 1
                        current_value -= self.values[i]
        
        return proposal