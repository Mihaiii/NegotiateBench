import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.turn_idx = 0
        self.total_val = sum(c * v for c, v in zip(counts, values))
        
        # Track cumulative count of items the opponent kept to estimate their interest.
        # Initialized to 0.0.
        self.opp_counts = [0.0] * len(counts)

    def offer(self, o: list[int] | None) -> list[int] | None:
        my_global_turn = self.me + 2 * self.turn_idx
        turns_left = self.total_turns - my_global_turn
        
        # --- 1. Update Opponent Model ---
        if o:
            incoming_val = sum(o[i] * self.values[i] for i in range(len(o)))
            # If they offered 'o', they kept 'counts - o'.
            for i in range(len(self.counts)):
                self.opp_counts[i] += (self.counts[i] - o[i])
        else:
            incoming_val = 0

        # --- 2. End-Game termination for Player 1 ---
        # If I am P1 and this is the absolute last turn of the game, 
        # I cannot counter (negotiation would fail). I must accept.
        if turns_left == 1:
            if o is not None:
                return None

        # --- 3. Determine Dynamic Target Value ---
        progress = my_global_turn / max(1, self.total_turns)
        
        # Base Concession Curve: Hold firm (100-95%) for most of the game.
        if progress < 0.2: 
            target_pct = 1.0
        elif progress < 0.7: 
            target_pct = 0.95
        else: 
            target_pct = 0.85

        # Tactical Overrides based on remaining turns
        if turns_left <= 4:
            target_pct = 0.80
            
        # P0 Ultimatum (Turn N-2): I am P0. Next turn P1 MUST accept or die. 
        # I demand a lot (90%), leaving them crumbs.
        if turns_left == 2:
            target_pct = 0.90
            
        # P1 Pre-Ultimatum (Turn N-3): I am P1. Next turn P0 moves. 
        # I must act reasonably now to avoid P0's ultimatum next turn.
        if turns_left == 3:
            target_pct = 0.70

        target_val = int(self.total_val * target_pct)

        # --- 4. Acceptance Logic ---
        if o is not None:
            # A. Value meets our target
            if incoming_val >= target_val:
                return None
            # B. Panic Accept: Deep in end-game, accept any 'decent' offer 
            # (65%+) to avoid getting 0 points from a failed negotiation.
            if turns_left <= 3 and incoming_val >= self.total_val * 0.65:
                return None

        # --- 5. Construct Counter-Offer ---
        # Strategy: Start with ALL items (max value).
        # Give back items one by one until we hit 'target_val'.
        # Order of giving back: Items with Lowest (My Value / Opponent Interest).
        # This keeps items I love and they hate, and gives away items they love and I hate.
        
        my_offer = list(self.counts)
        curr_val = self.total_val
        
        # Calculate efficiency ratios
        items_priority = []
        for i in range(len(self.counts)):
            # Add 1.0 to weight to avoid division by zero and smooth initial estimates
            opp_w = 1.0 + self.opp_counts[i]
            
            # Ratio: My Value per unit of Opponent Interest
            # Low Ratio = "Cheap for me to give, Valuable for them to get" -> Give these first.
            ratio = self.values[i] / opp_w
            
            # Add tiny noise to prevent deterministic loops in negotiation
            ratio += random.uniform(-1e-5, 1e-5)
            items_priority.append((ratio, i))
            
        # Sort Ascending (Lowest ratio first)
        items_priority.sort(key=lambda x: x[0])
        
        for _, i in items_priority:
            # If item is worthless to me, give it all away immediately
            if self.values[i] == 0:
                my_offer[i] = 0
                continue
                
            # Otherwise, decrement count until we reach the target floor
            while my_offer[i] > 0 and (curr_val - self.values[i]) >= target_val:
                my_offer[i] -= 1
                curr_val -= self.values[i]

        self.turn_idx += 1
        return my_offer