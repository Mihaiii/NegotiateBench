class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.round_num = 0
        self.acceptance_threshold = self.total_value / 2
        
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.round_num += 1
        current_round = self.round_num
        
        # If this is a counter-offer from partner
        if o is not None:
            # Calculate value of partner's offer to me
            offer_value = sum(o[i] * self.values[i] for i in range(len(o)))
            
            # If offer meets or exceeds our threshold, accept it
            if offer_value >= self.acceptance_threshold:
                return None
                
            # If we're in the final round, be more willing to accept
            total_turns = self.max_rounds * 2
            if current_round >= total_turns - 1:
                # In the last possible turn, accept anything better than 0
                if offer_value > 0:
                    return None
        
        # Generate counter-offer
        # Start with demanding everything we value
        proposal = self.counts.copy()
        
        # If we're going first, we can be more aggressive initially
        # If we're going second, we need to be slightly more reasonable from the start
        
        # Adjust based on round number - become more flexible as rounds progress
        rounds_remaining = self.max_rounds * 2 - current_round
        flexibility = 1.0 - (rounds_remaining / (self.max_rounds * 2))
        
        # Calculate minimum acceptable value based on flexibility
        min_acceptable = self.total_value * (0.5 - 0.3 * flexibility)
        
        # Try to find a reasonable counter-offer
        # Start with our ideal proposal and adjust if needed
        ideal_proposal = []
        for i in range(len(self.counts)):
            if self.values[i] > 0:
                ideal_proposal.append(self.counts[i])
            else:
                ideal_proposal.append(0)
        
        # If we're not in the first round or we're being too greedy, adjust
        if current_round > 1 or (self.me == 1 and current_round == 1):
            # Make a slightly more reasonable offer by giving up some low-value items
            # or items we have in abundance
            adjusted_proposal = ideal_proposal.copy()
            
            # Sort items by value per unit (descending) to prioritize keeping high-value items
            item_indices = sorted(range(len(self.values)), key=lambda i: self.values[i], reverse=True)
            
            # If we need to make concessions, start with items that have lower value to us
            for i in reversed(item_indices):
                if self.values[i] == 0:
                    adjusted_proposal[i] = 0
                elif self.values[i] > 0 and self.counts[i] > 1:
                    # Keep at least half of valuable items, rounded up
                    keep_amount = (self.counts[i] + 1) // 2
                    # But don't go below what would give us our minimum acceptable value
                    current_value = sum(adjusted_proposal[j] * self.values[j] for j in range(len(adjusted_proposal)))
                    if current_value > min_acceptable:
                        # We can afford to give up more
                        give_up_amount = min(self.counts[i] - keep_amount, 
                                           max(0, int((current_value - min_acceptable) / self.values[i])))
                        adjusted_proposal[i] = self.counts[i] - give_up_amount
            
            proposal = adjusted_proposal
        
        return proposal