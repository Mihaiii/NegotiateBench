import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        
        # Total number of turns in the game (my turns + opponent turns)
        self.total_turns = max_rounds * 2
        self.n_types = len(counts)
        self.my_total_val = sum(c * v for c, v in zip(counts, values))
        
        # State tracking
        self.turn_count = 0
        # Track cumulative count of items the opponent KEPT to estimate their preferences
        self.opp_kept_sum = [0] * self.n_types

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Calculate global turn index: 0, 1, 2, ...
        # If me=0: 0, 2, 4... | If me=1: 1, 3, 5...
        current_global_turn = self.me + self.turn_count * 2
        turns_left = self.total_turns - current_global_turn
        
        # --- 1. Update Opponent Model ---
        if o is not None:
            # If they offered 'o' to me, they kept 'counts - o' for themselves.
            for i in range(self.n_types):
                self.opp_kept_sum[i] += (self.counts[i] - o[i])
            
            # Calculate value of the incoming offer
            incoming_val = sum(o[i] * self.values[i] for i in range(self.n_types))
        else:
            incoming_val = 0

        # --- 2. End-Game Forced Acceptance ---
        # If this is the absolute last turn of the game (turn N-1), any counter-offer 
        # results in "No Deal" (0 value). We must accept anything provided we got an offer.
        if turns_left == 1:
            if o is not None:
                return None

        # --- 3. Determine Dynamic Target Value ---
        # Strategy:
        # - Early Game: Anchor high (100%).
        # - Mid Game: Concede slightly (92%).
        # - Late Game: Seek reasonable split (75%).
        # - Ultimatum/Panic: Drop to ensures deal (60-65%).
        
        progress = current_global_turn / max(1, self.total_turns)
        
        if progress < 0.35:
            target_pct = 1.0     # Firm hold
        elif progress < 0.70:
            target_pct = 0.92    # Slight concession
        else:
            target_pct = 0.75    # Cooperative zone
            
        # Tactical overrides near the deadline
        if turns_left <= 4:
            # Getting dangerous. Drop target to ensure we cross the gap.
            target_pct = 0.65
            
        if turns_left <= 2:
            # Final ultimatum opportunity (if acting now). Must be enticing.
            target_pct = 0.60
            
        target_val = int(self.my_total_val * target_pct)

        # --- 4. Acceptance Logic ---
        if o is not None:
            # A. Rational Acceptance: Offer meets our current aspiration level
            if incoming_val >= target_val:
                return None
            
            # B. Panic Acceptance: Deep in endgame, accept any reputable offer (>65%)
            # to avoid the risk of total failure (0 points). 
            # This catches cases where our target calc was slightly too strict.
            if turns_left <= 4 and incoming_val >= self.my_total_val * 0.65:
                return None

        # --- 5. Construct Counter-Offer ---
        # Goal: Form a bundle worth >= target_val.
        # Heuristic: Keep items I value highly but opponent values poorly.
        # Give away items I value poorly but opponent values highly.
        
        # Start with maximizing my utility (Keep everything)
        my_offer_counts = list(self.counts)
        current_proposal_val = self.my_total_val
        
        # Calculate prioritization metric for each item type
        priorities = []
        for i in range(self.n_types):
            # Estimate Opponent Interest: Sum of counts they kept so far.
            # Add small epsilon (0.1) to avoid division by zero and handle initial unknowns.
            opp_interest = self.opp_kept_sum[i] + 0.1
            
            # Ratio: My Cost (Value) / Opponent Benefit (Interest)
            # Low Ratio = "Cheap for me to give, Expensive for them to lose" -> Give these first.
            ratio = self.values[i] / opp_interest
            
            # Add negligible noise to prevent deterministic infinite loops 
            # if both agents have identical deterministic logic.
            ratio *= random.uniform(0.98, 1.02)
            
            priorities.append((ratio, i))
            
        # Sort ascending: Items with lowest ratio (Best to give away) come first
        priorities.sort(key=lambda x: x[0])
        
        # Iteratively give items away until we hit the target value floor
        for _, i in priorities:
            # If item is worthless to me, give all of them immediately
            if self.values[i] == 0:
                amount_to_give = my_offer_counts[i]
            else:
                # Calculate max amount we can give without dropping below target
                # (current - give * val) >= target  =>  give <= (current - target) / val
                max_give = (current_proposal_val - target_val) // self.values[i]
                amount_to_give = min(my_offer_counts[i], int(max_give))
            
            if amount_to_give > 0:
                my_offer_counts[i] -= amount_to_give
                current_proposal_val -= amount_to_give * self.values[i]
            
            # If we are already at or potentially below target (due to block release), stop.
            # (Note: Integer division ensures we stay >= target usually, loops just fills gap)
            if current_proposal_val <= target_val:
                break
                
        self.turn_count += 1
        return my_offer_counts