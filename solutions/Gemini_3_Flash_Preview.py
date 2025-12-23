class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.turn_count = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Sort indices by personal value descending
        self.indices_by_value = sorted(
            range(len(counts)), 
            key=lambda i: self.values[i], 
            reverse=True
        )

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        
        if o is not None:
            offer_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # Acceptance Thresholds
            # We want to be ambitious early but realistic as the deadline approaches.
            # In the very first few turns, we only accept if the value is extremely high.
            # As we approach the end, we scale down to a fair split (50%).
            progress = self.turn_count / self.total_turns
            
            if progress < 0.2:
                threshold = 0.9 * self.total_value
            elif progress < 0.5:
                threshold = 0.7 * self.total_value
            elif progress < 0.8:
                threshold = 0.6 * self.total_value
            else:
                threshold = 0.5 * self.total_value

            # Final turn safety: if we are about to walk away with zero, take what we can get
            # if it's better than nothing, but only on the absolute last turn for us.
            if self.turn_count >= self.total_turns - 1:
                if offer_value > 0:
                    return None
            
            if offer_value >= threshold:
                return None

        # Counter-offer Logic:
        # Determine target based on time remaining.
        # Start by asking for everything beneficial, then slowly concede items 
        # that are least valuable to us.
        if self.turn_count <= 2:
            target_value = self.total_value
        else:
            # Linear decay from 95% to 60% of total value
            target_ratio = 0.95 - (0.35 * (self.turn_count / self.total_turns))
            target_value = self.total_value * target_ratio

        my_offer = [0] * len(self.counts)
        current_val = 0
        
        # Priority 1: Take all items where our value is high.
        # Priority 2: In early sequences, we play "hardball" by keeping items
        # even if they have 0 value to us, to use as bargaining chips.
        for i in self.indices_by_value:
            for _ in range(self.counts[i]):
                # Always take if it doesn't push us over target, 
                # or if we need to reach the minimum target value.
                if current_val < target_value:
                    my_offer[i] += 1
                    current_val += self.values[i]
                else:
                    break
        
        # Strategic concession: In the middle of negotiation, if we have items 
        # with 0 value to us, don't ask for all of them. This signals "giving" 
        # something to the partner that might be highly valued by them.
        if self.turn_count > self.total_turns * 0.3:
            for i in range(len(my_offer)):
                if self.values[i] == 0:
                    # Half of zero-value items (rounded down) are conceded
                    my_offer[i] = self.counts[i] // 2

        # Final check: return at least one item
        if sum(my_offer) == 0:
            my_offer[self.indices_by_value[0]] = 1
            
        return my_offer