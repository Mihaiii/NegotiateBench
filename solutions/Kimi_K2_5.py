class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.n = len(counts)
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Initialize opponent estimates - assume uniform distribution
        total_items = sum(counts)
        avg_val = self.total_value / total_items if total_items > 0 else 0
        self.opp_est = [avg_val] * self.n
        
        self.turn_count = 0  # Tracks how many times we've been called
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        # Calculate absolute position in the negotiation
        abs_turn = self.turn_count * 2 + self.me
        total_turns = self.max_rounds * 2
        is_last_turn = (abs_turn == total_turns - 1)
        current_round = abs_turn // 2
        
        # Process received offer
        if o is not None:
            offer_val = sum(a * b for a, b in zip(o, self.values))
            
            # Update opponent value estimates
            # o[i] is what they offer me, counts[i] - o[i] is what they keep
            for i in range(self.n):
                if self.counts[i] == 0:
                    continue
                kept = self.counts[i] - o[i]
                keep_ratio = kept / self.counts[i]
                # Higher keep ratio implies higher value to them
                implied_val = keep_ratio * (self.total_value / sum(self.counts)) * 2
                self.opp_est[i] = 0.7 * self.opp_est[i] + 0.3 * implied_val
            
            # Acceptance logic with decreasing threshold
            if is_last_turn:
                if offer_val > 0:
                    self.turn_count += 1
                    return None
            else:
                # Threshold drops from 75% to 30% over the course of negotiations
                progress = current_round / (self.max_rounds - 1) if self.max_rounds > 1 else 0
                threshold = self.total_value * (0.75 - 0.45 * progress)
                if offer_val >= threshold:
                    self.turn_count += 1
                    return None
        
        # If last turn and we can't accept (no offer or zero offer), accept to avoid impasse
        if is_last_turn and o is not None:
            self.turn_count += 1
            return None
        
        # Generate counter-offer
        # Calculate concession level - we become more generous over time
        progress = current_round / (self.max_rounds - 1) if self.max_rounds > 1 else 0
        target_value = self.total_value * (0.70 - 0.30 * progress)  # 70% -> 40%
        
        # Sort items by net gain: items I value highly minus items they value highly
        # Prioritize items with high value to me and low estimated value to opponent
        item_scores = []
        for i in range(self.n):
            net_benefit = self.values[i] - self.opp_est[i]
            item_scores.append((net_benefit, i))
        
        item_scores.sort(reverse=True)
        
        # Greedy allocation based on sorted priorities
        my_offer = [0] * self.n
        current_value = 0
        
        for _, i in item_scores:
            if current_value >= target_value:
                break
            if self.values[i] == 0:
                continue  # Skip worthless items unless forced
            
            # Calculate how many we need
            remaining = target_value - current_value
            needed = int(remaining // self.values[i]) + 1
            take = min(needed, self.counts[i])
            
            my_offer[i] = take
            current_value += take * self.values[i]
        
        # If we still haven't reached target, fill with zero-value items (doesn't hurt)
        if current_value < target_value:
            for i in range(self.n):
                if current_value >= target_value:
                    break
                if self.values[i] == 0 and self.counts[i] > my_offer[i]:
                    my_offer[i] = self.counts[i]  # Take all worthless items
        
        self.turn_count += 1
        return my_offer