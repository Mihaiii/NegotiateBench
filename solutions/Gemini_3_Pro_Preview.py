import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.n_types = len(counts)
        self.my_max_val = sum(c * v for c, v in zip(counts, values))
        
        # Track what the opponent keeps (counts - offered_to_me) to estimate their preferences.
        self.opp_kept_sum = [0] * self.n_types
        # Log local turns to track game progress
        self.turn_count = 0

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Calculate global turn index (0 to total_turns - 1)
        # My turns are 0, 2, 4... (if me=0) or 1, 3, 5... (if me=1)
        global_turn = 2 * self.turn_count + self.me
        turns_left = self.total_turns - global_turn
        
        # --- 1. Update Opponent Model ---
        if o is not None:
            # Determine value of the offer to me
            incoming_val = sum(o[i] * self.values[i] for i in range(self.n_types))
            
            # Infer what items the opponent kept for themselves
            # o[i] is what they gave me; counts[i] - o[i] is what they kept.
            for i in range(self.n_types):
                kept_by_opp = self.counts[i] - o[i]
                if kept_by_opp > 0:
                    self.opp_kept_sum[i] += kept_by_opp
        else:
            incoming_val = 0

        self.turn_count += 1
        
        # --- 2. End-Game Forced Acceptance ---
        # If this is the absolute last turn of the session (turn index 2N-1),
        # making a counter-offer results in NO DEAL (0 points).
        # We must accept any offer to get a non-zero score.
        if turns_left == 1:
            if o is not None:
                return None
        
        # --- 3. Determine Dynamic Target Value ---
        # Decay aspiration level (target_pct) based on game progress to find the ZOPA (Zone of Possible Agreement).
        progress = global_turn / max(1, self.total_turns)
        
        if progress < 0.2:
            target_pct = 1.0     # Anchor high initially
        elif progress < 0.5:
            target_pct = 0.90    # Start conceding slowly
        elif progress < 0.8:
            target_pct = 0.75    # Seek compromise
        else:
            target_pct = 0.60    # Close to deadline, accept fair split
            
        # Panic override: Ensure we secure a deal in the final few turns
        if turns_left <= 4:
            target_pct = 0.55
        
        target_val = int(self.my_max_val * target_pct)
        
        # --- 4. Check Acceptance ---
        if o is not None:
            if incoming_val >= target_val:
                return None
            
        # --- 5. Construct Counter-Offer ---
        # Strategy: Keep items that are valuable to US and (seemingly) NOT interesting to THEM.
        # Metric: MyValue / OpponentInterest
        
        metrics = []
        for i in range(self.n_types):
            val_me = self.values[i]
            # Proxy for opponent interest: total count they kept so far.
            # Add epsilon to avoid division by zero.
            interest = self.opp_kept_sum[i] + 0.1
            
            # Ratio representing "Value lost by me per unit of interest satisfied for opponent"
            # Low ratio = Good item to give away to sweeten the deal.
            ratio = val_me / interest
            
            # Add negligible noise to prevent deterministic looping in bot-vs-bot
            ratio *= random.uniform(0.98, 1.02)
            
            metrics.append((ratio, i))
            
        # Sort by ratio ascending (Cheapest/Best items to give away come first)
        metrics.sort(key=lambda x: x[0])
        
        # Start by assuming we keep everything, then give away items until we hit our target floor.
        my_offer_counts = list(self.counts)
        current_proposal_val = self.my_max_val
        
        for _, i in metrics:
            # If item is worthless to me, give all of them immediately
            if self.values[i] == 0:
                n_give = my_offer_counts[i]
            else:
                # Calculate max amount we can give without dropping below target_val
                # current_val - (give * unit_val) >= target
                if current_proposal_val <= target_val:
                    n_give = 0
                else:
                    max_give = (current_proposal_val - target_val) // self.values[i]
                    n_give = min(my_offer_counts[i], int(max_give))
            
            if n_give > 0:
                my_offer_counts[i] -= n_give
                current_proposal_val -= n_give * self.values[i]
        
        return my_offer_counts