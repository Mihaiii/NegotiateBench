class Agent:
    def __init__(self, me, counts, values, max_rounds):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.n = len(counts)
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        self.turn = 0
        
        # Initialize opponent values with uniform distribution
        total_items = sum(counts)
        if total_items > 0:
            uniform = self.total_value / total_items
            self.opp_values = [uniform] * self.n
        else:
            self.opp_values = [0] * self.n
    
    def offer(self, o):
        # Calculate position in negotiation
        total_turns = self.max_rounds * 2
        turns_remaining = total_turns - self.turn - 1
        is_last_turn = (turns_remaining == 0)
        
        # Process received offer
        if o is not None:
            offer_value = sum(a * b for a, b in zip(o, self.values))
            
            # Update opponent model based on their offer
            for i in range(self.n):
                if self.counts[i] == 0:
                    continue
                given = o[i]
                kept = self.counts[i] - given
                
                if kept == self.counts[i]:
                    # They kept all - high value to them
                    self.opp_values[i] = max(self.opp_values[i] * 1.3, self.values[i] * 0.8)
                elif given == self.counts[i]:
                    # They gave all away - low value
                    self.opp_values[i] *= 0.4
                else:
                    # Partial - moderate update
                    ratio = kept / self.counts[i]
                    self.opp_values[i] = 0.8 * self.opp_values[i] + 0.2 * self.opp_values[i] * ratio * 1.5
            
            # Acceptance logic
            if is_last_turn:
                if offer_value > 0:
                    self.turn += 1
                    return None
            else:
                # Threshold drops from 65% to 20%
                progress = self.turn / (total_turns - 1) if total_turns > 1 else 0
                threshold = self.total_value * (0.65 - 0.45 * progress)
                
                if offer_value >= threshold:
                    self.turn += 1
                    return None
        
        # Generate counter-offer
        # Target drops from 75% to 25%
        progress = self.turn / (total_turns - 1) if total_turns > 1 else 0
        target = self.total_value * (0.75 - 0.5 * progress)
        
        # Sort by net value: my_value - 0.5 * opp_value
        # Prioritize items valuable to me, not valuable to opponent
        items = []
        for i in range(self.n):
            my_val = self.values[i]
            opp_val = self.opp_values[i]
            score = my_val - 0.5 * opp_val
            items.append((score, my_val, i))
        
        items.sort(reverse=True)
        
        # Greedy allocation
        my_offer = [0] * self.n
        current = 0
        
        for score, my_val, i in items:
            if current >= target:
                break
            if my_val <= 0:
                continue
            
            need = (target - current + my_val - 1) // my_val
            take = min(need, self.counts[i])
            my_offer[i] = take
            current += take * my_val
        
        # Give away zero-value items
        for i in range(self.n):
            if self.values[i] == 0:
                my_offer[i] = 0
        
        # Validate
        for i in range(self.n):
            my_offer[i] = max(0, min(my_offer[i], self.counts[i]))
        
        self.turn += 1
        return my_offer