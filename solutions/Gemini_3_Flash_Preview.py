class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.turn_count = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Sort indices by personal value descending for efficient allocation
        self.indices_by_value = sorted(
            range(len(counts)), 
            key=lambda i: self.values[i], 
            reverse=True
        )

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        
        # Calculate current offer value if it exists
        offer_value = 0
        if o is not None:
            offer_value = sum(o[i] * self.values[i] for i in range(len(o)))

        # Determine if we should accept
        # progress goes from 0 to 1
        progress = self.turn_count / self.total_turns
        
        if o is not None:
            # Acceptance Thresholds: Stay firm early, compromise late.
            if progress < 0.2:
                threshold = 0.95 * self.total_value
            elif progress < 0.5:
                threshold = 0.8 * self.total_value
            elif progress < 0.8:
                threshold = 0.7 * self.total_value
            elif progress < 0.95:
                threshold = 0.6 * self.total_value
            else:
                # In the absolute final turns, accept anything above a fair floor
                threshold = 0.5 * self.total_value if self.total_value > 0 else 0
            
            # Final turn logic: if we are Agent 1 (second mover) and it's the last turn
            if self.turn_count == self.total_turns:
                if offer_value > 0:
                    return None
            
            if offer_value >= threshold and offer_value > 0:
                return None

        # Counter-offer Logic:
        # Determine target based on time remaining using a non-linear decay.
        if progress < 0.1:
            target_ratio = 1.0
        elif progress < 0.4:
            target_ratio = 0.9
        elif progress < 0.7:
            target_ratio = 0.8
        elif progress < 0.9:
            target_ratio = 0.7
        else:
            target_ratio = 0.6

        target_value = self.total_value * target_ratio
        
        my_offer = [0] * len(self.counts)
        current_val = 0
        
        # 1. Fill offer with high value items first
        for i in self.indices_by_value:
            if self.values[i] > 0:
                for _ in range(self.counts[i]):
                    if current_val < target_value:
                        my_offer[i] += 1
                        current_val += self.values[i]
                    else:
                        break
        
        # 2. Strategic "Bargaining Chips": 
        # In early/mid stages, hold onto items with 0 value to us.
        # This forces the opponent to "pay" to get them if they value them.
        if progress < 0.5:
            # Demand all zero-value items early
            for i in range(len(self.counts)):
                if self.values[i] == 0:
                    my_offer[i] = self.counts[i]
        elif progress < 0.85:
            # Start conceding zero-value items
            for i in range(len(self.counts)):
                if self.values[i] == 0:
                    my_offer[i] = self.counts[i] // 2
        else:
            # Concede all zero-value items at the end to bridge the gap
            for i in range(len(self.counts)):
                if self.values[i] == 0:
                    my_offer[i] = 0

        # Safety: Ensure we aren't asking for more than exists
        for i in range(len(my_offer)):
            my_offer[i] = min(my_offer[i], self.counts[i])

        # Final check: Don't return an offer worth nothing if we can help it
        if sum(m * v for m, v in zip(my_offer, self.values)) == 0 and self.total_value > 0:
            my_offer[self.indices_by_value[0]] = 1
            
        return my_offer