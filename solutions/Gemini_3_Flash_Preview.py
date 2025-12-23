class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.turn_count = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Priority for items: value to us first, then low counts (easier to trade)
        self.indices = sorted(
            range(len(counts)), 
            key=lambda i: (self.values[i], -self.counts[i] if self.counts[i] > 0 else 0), 
            reverse=True
        )

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        
        # Calculate the value of the opponent's offer to us
        offer_value = sum(o[i] * self.values[i] for i in range(len(o))) if o is not None else 0
        
        # progress goes from 0 to 1
        progress = self.turn_count / self.total_turns
        
        # 1. EVALUATE ACCEPTANCE
        if o is not None:
            # Acceptance threshold logic: be very demanding early, realistic late
            if progress < 0.2:
                threshold = 1.0 * self.total_value
            elif progress < 0.5:
                threshold = 0.85 * self.total_value
            elif progress < 0.75:
                threshold = 0.70 * self.total_value
            elif progress < 0.9:
                threshold = 0.60 * self.total_value
            else:
                # In the final steps, accept anything that isn't a total loss
                # Especially if we are the second person to act (turn_count == total_turns)
                threshold = 0.45 * self.total_value if self.total_value > 0 else 0

            # Last-chance logic for Agent 1
            if self.turn_count >= self.total_turns - 1:
               if offer_value > 0 or self.total_value == 0:
                   return None

            if offer_value >= threshold:
                return None

        # 2. GENERATE COUNTER-OFFER
        # Aim for a target value based on progress
        if progress < 0.3:
            target_val = self.total_value
        elif progress < 0.6:
            target_val = 0.9 * self.total_value
        elif progress < 0.8:
            target_val = 0.8 * self.total_value
        else:
            target_val = 0.7 * self.total_value

        my_offer = [0] * len(self.counts)
        current_val = 0
        
        # Fill high-value items first
        for i in self.indices:
            if self.values[i] > 0:
                for _ in range(self.counts[i]):
                    if current_val < target_val:
                        my_offer[i] += 1
                        current_val += self.values[i]
                    else:
                        break
        
        # 3. STRATEGIC BARGAINING (Zeroling)
        # We hold onto items that are worth 0 to us early to use as "concessions" later
        if progress < 0.4:
            # Demand everything we value AND everything we don't
            for i in range(len(self.counts)):
                if self.values[i] == 0:
                    my_offer[i] = self.counts[i]
        elif progress < 0.8:
            # Start giving away half of the things we don't value
            for i in range(len(self.counts)):
                if self.values[i] == 0:
                    my_offer[i] = self.counts[i] // 2
        else:
            # Last stage: Give away everything we don't value to please the partner
            for i in range(len(self.counts)):
                if self.values[i] == 0:
                    my_offer[i] = 0

        # Safety Check: Never offer more than counts
        for i in range(len(my_offer)):
            my_offer[i] = min(my_offer[i], self.counts[i])

        # Final check: Don't return a zero offer unless the total value is actually 0
        if sum(m * v for m, v in zip(my_offer, self.values)) == 0 and self.total_value > 0:
            # Determine the index of our most valuable item
            best_idx = self.indices[0]
            my_offer[best_idx] = 1

        return my_offer