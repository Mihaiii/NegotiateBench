class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.round = 0
        # Estimate opponent's valuation to find mutually beneficial trades
        n = len(counts)
        avg_value = self.total_value / sum(counts) if sum(counts) > 0 else 0
        self.opp_est = [avg_value] * n
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        # Check if this is the final turn (only applies when me==1)
        is_last_turn = (self.me == 1 and self.round == self.max_rounds - 1)
        
        if o is not None:
            offer_value = sum(a * b for a, b in zip(o, self.values))
            
            # Update opponent value estimates based on what they kept
            for i in range(len(self.counts)):
                if self.counts[i] > 0:
                    kept = self.counts[i] - o[i]
                    # Higher proportion kept suggests higher value to opponent
                    prop = kept / self.counts[i]
                    self.opp_est[i] = 0.7 * self.opp_est[i] + 0.3 * prop * (self.total_value / sum(self.counts))
            
            # Acceptance logic with deadline effect
            if is_last_turn:
                # Accept anything positive to avoid getting 0
                if offer_value > 0:
                    return None
            else:
                # Threshold decreases from 70% to 25% over rounds
                if self.max_rounds > 1:
                    threshold = self.total_value * (0.70 - 0.45 * self.round / (self.max_rounds - 1))
                else:
                    threshold = self.total_value * 0.5
                
                if offer_value >= threshold:
                    return None
        
        # If last turn and we didn't accept (offer was 0 or we skipped), accept to end gracefully
        if is_last_turn:
            return None
            
        # Generate counter-offer
        # Target decreases from 60% to 30% as we become more desperate
        if self.max_rounds > 1:
            target = self.total_value * (0.60 - 0.30 * self.round / (self.max_rounds - 1))
        else:
            target = self.total_value * 0.4
            
        # Prioritize items with high value to me and low estimated value to opponent
        indices = list(range(len(self.counts)))
        indices.sort(key=lambda i: self.values[i] / (self.opp_est[i] + 0.01), reverse=True)
        
        my_offer = [0] * len(self.counts)
        current_value = 0
        
        for i in indices:
            if current_value >= target:
                break
            # Take as many as needed to approach target
            need = int((target - current_value) // max(self.values[i], 1)) + 1
            take = min(need, self.counts[i])
            my_offer[i] = take
            current_value += take * self.values[i]
        
        # Fill remaining if still below target
        if current_value < target:
            for i in indices:
                if current_value >= target:
                    break
                remaining = self.counts[i] - my_offer[i]
                if remaining > 0:
                    my_offer[i] += remaining
                    current_value += remaining * self.values[i]
        
        self.round += 1
        return my_offer