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
        
        # Opponent modeling
        # We track total frequency of items the opponent KEEPS.
        self.opp_kept_freq = [0.0] * self.n
        self.opp_offers_seen = 0
        # Weights initialized to 1.0; will be updated to sum to self.my_max_val
        self.opp_weights = [1.0] * self.n
        
        self.turns_played = 0

    def offer(self, o: list[int] | None) -> list[int] | None:
        # --- 1. Update Opponent Model ---
        if o is not None:
            self.opp_offers_seen += 1
            # o is what I get. Opponent keeps remaining = counts - o
            for i in range(self.n):
                kept = self.counts[i] - o[i]
                self.opp_kept_freq[i] += kept
                
        # Update valus estimates (weights)
        if self.opp_offers_seen > 0:
            raw_weights = []
            for i in range(self.n):
                # Avoid division by zero
                c = self.counts[i] if self.counts[i] > 0 else 1
                # Weight proportional to frequency of keeping
                # Add prior (0.5) to smooth early volatility
                prob = (self.opp_kept_freq[i] + 0.5) / (self.opp_offers_seen * c + 1.0)
                raw_weights.append(prob)
            
            # Normalize so that Sum(weight * count) matches my total value (Symmetry assumption)
            est_total = sum(raw_weights[i] * self.counts[i] for i in range(self.n))
            if est_total > 0:
                factor = self.my_max_val / est_total
                self.opp_weights = [w * factor for w in raw_weights]
            else:
                self.opp_weights = [1.0] * self.n # Fallback

        # --- 2. Calculate Game State ---
        # Turns are 0-indexed. 
        # Me=0 plays 0, 2, ...; Me=1 plays 1, 3, ...
        current_turn = self.turns_played * 2 + (1 if self.me == 1 else 0)
        remaining_turns = self.total_turns - current_turn
        progress = current_turn / self.total_turns
        
        # --- 3. Generate Strategy (Target & Offers) ---
        
        # Generate Pareto frontier approximation using Efficiency = MyVal / OppWeight
        pareto_points = self.get_pareto_options()
        
        # Identify the Nash Bargaining Solution point (Maximize MyVal * OppVal)
        best_nash_val = 0
        max_product = -1
        
        for my_v, opp_v, _ in pareto_points:
            prod = my_v * opp_v
            if prod > max_product:
                max_product = prod
                best_nash_val = my_v
        
        # Set Aspiration Level (Target Value) based on time
        # Curve: Start High -> Decay to Nash Point -> Hold -> Late Game Decay
        high_anchor = self.my_max_val
        
        if progress < 0.2:
            # Drop from Max to Nash
            ratio = progress / 0.2
            current_target = high_anchor * (1.0 - ratio) + best_nash_val * ratio
        elif progress < 0.8:
            # Hold at Nash (Fair Efficient Deal)
            current_target = best_nash_val
        else:
            # Late game concession: Decay from Nash to a safe Reservation price
            # Reservation: 75% of Nash or 40% of Total, whichever is higher
            res_price = max(best_nash_val * 0.75, self.my_max_val * 0.4)
            ratio = (progress - 0.8) / 0.2
            current_target = best_nash_val * (1.0 - ratio) + res_price * ratio

        # --- 4. Evaluate Incoming Offer ---
        val_o = 0
        if o is not None:
            val_o = sum(o[i] * self.values[i] for i in range(self.n))
            
            # a) Meets current aspiration
            if val_o >= current_target:
                return None
            
            # b) Is "Good Enough" (Close to Nash)?
            # If we are effectively at the efficient deal, accept even if target is slightly off due to float math
            if val_o >= best_nash_val * 0.98:
                return None
            
            # c) End Game Logic
            if remaining_turns <= 2:
                # If I am receiver in the very last turn (Turn N-1), Accept anything > 0.
                if remaining_turns == 1:
                    if val_o > 0:
                        return None
                else: 
                    # If I am deciding in Turn N-2 (my last chance to accept before making ultimatum),
                    # Accept if offer is decent (prevents accidental 0 outcome if opponent is stubborn)
                    if val_o >= self.my_max_val * 0.45:
                        return None

        # --- 5. Generate Counter-Offer ---
        
        # Special Case: Ultimatum Giver (Turn Total-2)
        # I make the absolute final offer. Opponent must accept > 0.
        if remaining_turns == 2:
            # Find pareto point that gives Opponent > 0 (and ideally a tiny bit more to be safe)
            # Pick the one that Maximizes MY value among those.
            ultimatum_cands = [p for p in pareto_points if p[1] > 0]
            if ultimatum_cands:
                best_ult = max(ultimatum_cands, key=lambda x: x[0])
                # If the current offer `o` is actually better for me than my calculated ultimatum, accept `o`
                if o is not None and val_o >= best_ult[0]:
                    return None
                
                self.turns_played += 1
                return best_ult[2]

        # Standard Case: Find best bundle satisfying Target
        # Filter points where MyVal >= Target
        candidates = [p for p in pareto_points if p[0] >= current_target]
        
        # If target is too high (above max possible), fallback to max possible
        if not candidates:
            candidates = [p for p in pareto_points if p[0] == self.my_max_val] # Start logic check
            if not candidates:
                # Should not happen given generate logic includes full set, but safe fallback
                candidates = pareto_points 

        # Among candidates satisfying my needs, pick the one maximizing Opponent Value
        # This increases likelihood of acceptance.
        best_offer = max(candidates, key=lambda x: x[1])
        
        proposal = best_offer[2]
        
        self.turns_played += 1
        return proposal

    def get_pareto_options(self):
        # Heuristic to generate Pareto frontier points
        # Sort items by "Efficiency" = MyValue / OpponentWeight
        # Items I like much more than Opponent does goes to Me.
        
        items = []
        for i in range(self.n):
            if self.counts[i] > 0:
                # Avoid div by zero
                w = max(self.opp_weights[i], 0.001)
                eff = self.values[i] / w
                # Flatten counts: treat each specific item individually
                for _ in range(self.counts[i]):
                    items.append({
                        'idx': i,
                        'eff': eff,
                        'val': self.values[i],
                        'w': w
                    })
        
        # Sort descending by efficiency
        items.sort(key=lambda x: x['eff'], reverse=True)
        
        points = []
        
        # Start state: I have 0 items, Opponent has All items
        total_opp_val = sum(self.opp_weights[i] * self.counts[i] for i in range(self.n))
        
        cur_my_val = 0
        cur_opp_val = total_opp_val
        cur_counts = [0] * self.n
        
        # Add 0-point
        points.append( (cur_my_val, cur_opp_val, list(cur_counts)) )
        
        # Greedily add items to my bundle
        for item in items:
            idx = item['idx']
            cur_counts[idx] += 1
            cur_my_val += item['val']
            cur_opp_val -= item['w']
            
            # Record point (MyVal, OppVal, MyPartion)
            points.append( (cur_my_val, max(0, cur_opp_val), list(cur_counts)) )
            
        return points