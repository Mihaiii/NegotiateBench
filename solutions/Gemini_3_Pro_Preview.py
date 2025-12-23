import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.rounds = max_rounds
        self.total_turns = max_rounds * 2
        # current_turn: 0, 1, 2, ... relative to the start of the session
        self.current_turn = me
        
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.max_val = self.total_value
        
        # Heuristic: Track opponent's cumulative 'keeps' to infer their valuation.
        # If they keep an item often, they value it.
        # Initialized to 0.
        self.opponent_interest = [0] * len(counts)

    def offer(self, o: list[int] | None) -> list[int] | None:
        if o:
            # Update opponent interest based on what they KEPT
            # They offered 'o' to me, so they kept 'counts - o'.
            for i, count_given in enumerate(o):
                kept_count = self.counts[i] - count_given
                self.opponent_interest[i] += kept_count

            # Calculate the value of the offer to me
            val_offered = sum(o[i] * self.values[i] for i in range(len(self.counts)))
            
            # Endgame Logic (Player 2, Last Turn)
            # If I am Player 2 and this is the absolute last turn of the game,
            # I must accept any proposal with positive value to avoid the count-out (0 payoff).
            if self.me == 1 and self.current_turn >= self.total_turns - 1:
                # Accept anything better than 0.
                if val_offered > 0:
                    return None
            
            # Standard Acceptance Logic
            # Retrieve dynamic aspiration level
            target = self._get_target_value()
            if val_offered >= target:
                return None

        # If we did not accept (or it's the first turn), generate a Counter-Offer.
        target = self._get_target_value()
        
        # Strategy: Pareto Improvement Heuristic
        # We want to compose a bundle for ourselves that meets 'target' value.
        # To make the offer attractive to the opponent, we should take items that
        # provide high value to us but low value to them (inferred from opponent_interest).
        # We sort items by efficiency: My Value / (Opponent Interest + epsilon)
        
        items_priority = []
        for i, val in enumerate(self.values):
            if val > 0:
                # Epsilon 1.0 reduces sensitivity to initial zeros.
                # Add small random jitter to break ties and avoid deterministic stale-mates.
                priority = val / (1.0 + self.opponent_interest[i])
                priority += random.uniform(0, 0.0001)
                items_priority.append((priority, i))
        
        # Sort descending (Higher priority -> Better to take)
        items_priority.sort(key=lambda x: x[0], reverse=True)
        
        my_offer = [0] * len(self.counts)
        current_sum = 0
        
        # Greedy Selection to meet Target
        for _, idx in items_priority:
            avail = self.counts[idx]
            item_val = self.values[idx]
            
            needed = target - current_sum
            if needed <= 0:
                break
                
            # Take just enough items of this type to progress efficiently
            # Ceiling division: (needed / item_val)
            take = (needed + item_val - 1) // item_val
            
            # Clamp to availability
            take = max(0, min(take, avail))
            
            my_offer[idx] += take
            current_sum += take * item_val
            
        # If the greedy fill failed to reach target (rare, unless target > max possible),
        # we still return the best bundle we made.
        
        # Update turn counter for next interaction (a round is 2 turns)
        self.current_turn += 2
        
        return my_offer

    def _get_target_value(self) -> int:
        # Returns the aspiration value (minimum acceptable value) for the current turn.
        # Maps time progress to a percentage of max value.
        
        # Progress 0.0 (start) to 1.0 (end of game)
        progress = self.current_turn / max(1, self.total_turns - 1)
        
        # Curve Strategy:
        # Phase 1: High Anchor (0% - 40% time): Ask for near 100%. Signals strength.
        # Phase 2: Concession (40% - 80% time): Drop linearly to ~80% max value.
        # Phase 3: Agreement (80% - 100% time): Drop to reservation (~60% max value).
        
        if progress < 0.4:
            pf = 1.0
        elif progress < 0.8:
            # Drop from 1.0 to 0.8
            ratio = (progress - 0.4) / 0.4
            pf = 1.0 - (0.2 * ratio)
        else:
            # Drop from 0.8 to 0.6
            ratio = (progress - 0.8) / 0.2
            pf = 0.8 - (0.2 * ratio)
            
        # Calculate integer target
        target = int(self.max_val * pf)
        
        # Sanity check: Ensure target is at least 1 if value exists (except in odd zero-value games)
        if target == 0 and self.max_val > 0:
            target = 1
            
        return target