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
            range(len(counts)), key=lambda i: self.values[i], reverse=True
        )

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        
        # Current value of partner's offer to me
        offer_val = sum(o[i] * self.values[i] for i in range(len(o))) if o is not None else 0
        
        # Progress from 0 to 1
        progress = self.turn_count / self.total_turns
        
        # 1. Evaluate Acceptance
        if o is not None:
            # Acceptance thresholds: 
            # Very high early on, decreasing towards the end
            if progress < 0.3:
                threshold = 0.95 * self.total_value
            elif progress < 0.6:
                threshold = 0.85 * self.total_value
            elif progress < 0.85:
                threshold = 0.70 * self.total_value
            else:
                # Last resort: accept slightly more than 50% or face 0
                threshold = 0.55 * self.total_value if self.total_value > 0 else 0

            # If it's the absolute last turn and we are index 1, we must accept any value > 0
            if self.me == 1 and self.turn_count >= self.total_turns:
                if offer_val > 0:
                    return None
            
            # If we are index 0, the last turn is turn_count == total_turns - 1
            if self.me == 0 and self.turn_count >= self.total_turns - 1:
                if offer_val > 0.4 * self.total_value:
                    return None

            if offer_val >= threshold and offer_val > 0:
                return None

        # 2. Determine Target Value for Counter-Offer
        # We start by demanding everything and slowly concede
        if progress < 0.4:
            target = self.total_value
        elif progress < 0.7:
            target = 0.9 * self.total_value
        elif progress < 0.9:
            target = 0.8 * self.total_value
        else:
            target = 0.65 * self.total_value

        # 3. Build the Counter-Offer
        my_offer = [0] * len(self.counts)
        current_val = 0
        
        # Greedily take high value items first
        for i in self.indices_by_value:
            if self.values[i] > 0:
                for _ in range(self.counts[i]):
                    if current_val < target:
                        my_offer[i] += 1
                        current_val += self.values[i]
                    else:
                        break
        
        # 4. Strategic "Filler" (Items worth 0 to us)
        # Demand items worth 0 to us early to have room to "concede" them later
        if progress < 0.5:
            for i in range(len(self.counts)):
                if self.values[i] == 0:
                    my_offer[i] = self.counts[i]
        elif progress < 0.85:
            for i in range(len(self.counts)):
                if self.values[i] == 0:
                    # Keep some to look like we are still negotiating
                    my_offer[i] = self.counts[i] // 2
        else:
            # Give away all 0-value items to maximize partner's utility
            for i in range(len(self.counts)):
                if self.values[i] == 0:
                    my_offer[i] = 0

        # Safety: ensure we don't return an empty offer if we have value to gain
        if sum(my_offer[i] * self.values[i] for i in range(len(my_offer))) == 0 and self.total_value > 0:
             my_offer[self.indices_by_value[0]] = 1

        return my_offer