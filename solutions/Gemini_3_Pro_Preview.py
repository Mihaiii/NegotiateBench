import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.n = len(counts)
        self.my_max_val = sum(c * v for c, v in zip(counts, values))
        
        # Opponent model: Weights estimated from frequency of opponent keeping items
        # Initialize with 1.0 (neutral)
        self.opp_weights = [1.0] * self.n 
        self.opp_kept_sum = [0] * self.n
        
        self.turns_played = 0

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Determine current global turn index (0 to total_turns-1)
        if self.me == 0:
            current_turn = self.turns_played * 2
        else:
            current_turn = self.turns_played * 2 + 1
            
        remaining_turns = self.total_turns - current_turn
        
        # Analyze incoming offer (o is what I get, so partner kept counts - o)
        val_o = 0
        if o is not None:
            val_o = sum(o[i] * self.values[i] for i in range(self.n))
            for i in range(self.n):
                kept = self.counts[i] - o[i]
                # Track cumulative count of items opponent retained
                if kept > 0:
                    self.opp_kept_sum[i] += kept
                    
        # Update opponent weights based on what they tend to keep
        total_kept = sum(self.opp_kept_sum)
        if total_kept > 0:
            for i in range(self.n):
                # Weight is proportional to frequency of keeping.
                # Factor 20.0 emphasizes observed preferences strongly over time.
                self.opp_weights[i] = 1.0 + (self.opp_kept_sum[i] / total_kept) * 20.0
        
        # --- Strategic Logic ---
        
        # 1. End Game: Ultimatum Receiver (Last Turn of the entire session)
        # If I am on the very last turn, rejecting/countering yields 0 for both.
        # Rational strategy: Accept any positive value.
        if remaining_turns == 1:
            if o is not None:
                if val_o > 0 or self.my_max_val == 0:
                    return None
                return None # Fallback accept to avoid timeout/0 result
        
        # 2. End Game: Ultimatum Giver (Second to Last Turn)
        # I make the final offer. Opponent must accept anything > 0 on their next turn.
        # Strategy: Offer 1 unit of the item they seem to value most, keep the rest.
        if remaining_turns == 2:
            best_opp_idx = 0
            max_w = -1.0
            # Identify item with highest estimated weight to opponent
            for i in range(self.n):
                if self.counts[i] > 0:
                    if self.opp_weights[i] > max_w:
                        max_w = self.opp_weights[i]
                        best_opp_idx = i
            
            ultimatum = list(self.counts)
            # Give them 1 of their favorite item
            if ultimatum[best_opp_idx] > 0:
                ultimatum[best_opp_idx] -= 1
            
            # If current offer o is better than my ruthless ultimatum, take o instead.
            ult_val = sum(ultimatum[i] * self.values[i] for i in range(self.n))
            if o is not None and val_o >= ult_val:
                return None
            
            self.turns_played += 1
            return ultimatum

        # 3. Standard Negotiation Phases
        
        # Calculate Reservation Price (Aspiration Level)
        # Curve: High plateau -> Linear decay -> Floor
        progress = current_turn / self.total_turns
        
        if progress < 0.5:
            # First half: Hold near max (100% -> 95%)
            factor = 1.0 - 0.05 * (progress / 0.5)
        elif progress < 0.9:
            # Negotiations active: Decay from 95% -> 70%
            p = (progress - 0.5) / 0.4
            factor = 0.95 - 0.25 * p
        else:
            # Panic phase: Decay from 70% -> 50%
            p = (progress - 0.9) / 0.1
            factor = 0.7 - 0.2 * p
            
        reservation = int(self.my_max_val * factor)
        # Ensure we don't accidentally set reservation to 0 if we have value available
        if reservation == 0 and self.my_max_val > 0:
            reservation = 1
            
        # Accept if offer meets reservation
        if o is not None and val_o >= reservation:
            return None
            
        # Generate Counter-Offer
        # Target is set slightly above reservation to allow room for concession
        target = int(reservation * 1.05)
        if target > self.my_max_val: 
            target = self.my_max_val
            
        # Optimization Goal: MINIMIZE Opponent's Pain (Sum of weights of items I take)
        # subject to MyValue >= Target.
        # This is equivalent to finding a bundle that Maximizes Opponent Utility 
        # while satisfying my greedy constraint.
        
        candidates = []
        # Candidate 1: Pure Greedy based on estimated weights
        candidates.append(self.get_greedy_offer(target, self.opp_weights))
        
        # Candidate 2-4: Noisy weights (Genetic variation to escape local optima)
        for _ in range(3):
            noisy_w = [w * random.uniform(0.8, 1.2) for w in self.opp_weights]
            candidates.append(self.get_greedy_offer(target, noisy_w))
            
        # Candidate 5: Try hitting exactly reservation (more generous to opp)
        candidates.append(self.get_greedy_offer(reservation, self.opp_weights))
        
        best_offer = None
        best_opp_metric = -1
        
        for cand in candidates:
            my_v = sum(cand[i] * self.values[i] for i in range(self.n))
            if my_v < reservation:
                continue # Skip if candidate generation failed to meet goal
            
            # Opponent utility metric: Sum of weights of items I did NOT take
            opp_metric = sum( (self.counts[i] - cand[i]) * self.opp_weights[i] for i in range(self.n) )
            
            if opp_metric > best_opp_metric:
                best_opp_metric = opp_metric
                best_offer = cand
                
        # Fallback if no candidate works
        if best_offer is None:
            best_offer = list(self.counts)
            
        # Sanity Check: Never offer something that gives me LESS than what's currently on the table.
        my_counter_val = sum(best_offer[i] * self.values[i] for i in range(self.n))
        if o is not None and val_o >= my_counter_val:
            return None
            
        self.turns_played += 1
        return best_offer

    def get_greedy_offer(self, target, weights):
        # We want to KEEP items that have high Efficiency = (MyValue / OpponentWeight).
        # This leaves items with low Efficiency (meaning Opponent wants them more than I do) for them.
        items = []
        for i in range(self.n):
            if self.values[i] > 0:
                # Avoid division by zero
                eff = self.values[i] / max(weights[i], 0.0001)
                items.append((eff, i))
        
        # Sort descending by efficiency
        items.sort(key=lambda x: x[0], reverse=True)
        
        proposal = [0] * self.n
        current_val = 0
        
        # Fill my bag until target is reached
        for _, i in items:
            if current_val >= target:
                break
                
            needed = target - current_val
            # Calculate number of items needed: ceil(needed / val)
            cnt = (needed + self.values[i] - 1) // self.values[i]
            take = min(self.counts[i], cnt)
            
            proposal[i] = take
            current_val += take * self.values[i]
            
        # If we exhausted preferences and still didn't reach target (very high target),
        # fill with remaining available value items.
        if current_val < target:
            for _, i in items:
                rem = self.counts[i] - proposal[i]
                if rem > 0:
                    proposal[i] += rem
                    current_val += rem * self.values[i]
                    
        return proposal