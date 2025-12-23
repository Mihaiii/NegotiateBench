class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.num_items = len(counts)
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.me = me
        self.max_rounds = max_rounds
        # History of offers made by the opponent (list of lists)
        self.history = []

    def offer(self, o: list[int] | None) -> list[int] | None:
        # Record opponent's offer if not None
        if o is not None:
            self.history.append(o)

        # Calculate remaining rounds including current turn
        # max_rounds is total rounds (pairs of turns). 
        # We can track rounds roughly by the length of history or a decrementing counter if implemented.
        # Here we approximate remaining turns based on history length and self.me.
        
        # Remaining turns = (max_rounds * 2) - turns_taken
        # turns_taken = len(self.history) + 1 (current turn)
        # Note: logic below is careful about who starts.
        
        turns_taken = len(self.history) + (1 if o is not None else 0)
        total_turns = self.max_rounds * 2
        
        # If I am first (me=0), I go on turns 0, 2, 4...
        # If I am second (me=1), I go on turns 1, 3, 5...
        # Current turn index is turns_taken - 1.
        # This is my turn if (turns_taken - 1) % 2 != self.me ? No.
        # Turn indices: 0, 1, 2, 3...
        # If me=0: 0, 2, 4.
        # If me=1: 1, 3, 5.
        # Offer method is called on my turn.
        # So if we are here, it IS my turn.
        # We just need to know how many MORE offers can be made after this one.
        
        # Determine if this is the very last offer in the negotiation.
        # If I accept, negotiation ends immediately.
        # If I offer, and it's not accepted, do we get another turn?
        # Only if turns_taken + 1 < total_turns.
        
        is_last_offer = (turns_taken >= total_turns)

        # Evaluate opponent's offer
        if o is not None:
            offer_val = sum(self.values[i] * o[i] for i in range(self.num_items))
            
            # Calculate dynamic threshold
            threshold = self.calculate_threshold(turns_taken, total_turns, is_last_offer)
            
            if offer_val >= threshold:
                return None  # Accept

        # If not accepting, generate a counter-offer
        return self.generate_offer()

    def calculate_threshold(self, turns_taken: int, total_turns: int, is_last_offer: bool) -> float:
        """
        Calculates the minimum value to accept based on game theory (Nash bargaining / Rubinstein)
        and competitive constraints.
        """
        # Theoretical share based on turn order and remaining rounds
        # Delta = discount factor (per round)
        # If I am first (me=0), I have advantage.
        # If I am second (me=1), I have disadvantage.
        
        # Simplified: 
        # First player asks for Total, second accepts 0 (in last round).
        # Previous round: First asks Total, Second accepts Total * delta (where delta ~ 1 here, but logically just Total).
        # With symmetric bargaining power, fair split is 0.5.
        # With turn order, it oscillates between 1.0 and 0.0.
        # We target the maximum of (Competitive Share) and (Fair Share * Risk Tolerance).
        
        # Fair share is total_value / 2
        fair_share = self.total_value / 2.0
        
        # Competitive share calculation
        # Determine how many "bargaining periods" are left.
        # A period is a pair of offers.
        turns_remaining = total_turns - turns_taken
        rounds_remaining = turns_remaining // 2
        
        # My base share if I drive a hard bargain
        if self.me == 0:
            # I offer first.
            # If rounds_remaining == 0 (meaning this is my last turn to offer before opponent accepts/rejects final),
            # I should ask for high value.
            # Actually, if is_last_offer, and I am responding to opponent's offer, I must accept if > 0 (or whatever I can get).
            # But the logic flow for o is not None handles response.
            # Here we calculate the threshold to ACCEPT.
            
            # If I am first player (me=0), and it's my turn to respond (o is not None),
            # I expect to get the high share in the NEXT round if I reject now (provided next round exists).
            # If I reject and no more rounds, I get 0.
            
            # If I am first player and responding:
            # If rounds_remaining >= 1, I can expect Total in my next offer. So I reject anything < Total.
            # But wait, the opponent knows this and will offer Total in their previous turn.
            # So I should accept Total.
            
            # Let's look at the structure again.
            # Me=0. Opponent offers. Rounds remaining = R.
            # If R > 0: I can offer next. I will demand Total. Opponent (if rational) will accept Total (if no further rounds).
            # So I should reject current offer unless it is Total.
            # If R = 0: This is the last turn. If I reject, I get 0. Accept if > 0.
            
            if rounds_remaining > 0:
                target_share = self.total_value
            else:
                target_share = 1 # > 0
        else:
            # I am second player (me=1). Opponent offers.
            # If rounds_remaining >= 1: I can offer next. I will demand Total.
            #   Opponent will get one more turn after me.
            #   If opponent gets last turn, they demand Total. I must accept 0.
            #   So if I offer Total now, opponent rejects (waiting for their turn to get Total).
            #   So I must accept whatever opponent offers that is better than my future outcome (0).
            #   Wait, if opponent offers X, and I reject, I offer Total. Opponent rejects. Opponent offers Total. I accept 0.
            #   So I should accept X > 0.
            # If rounds_remaining = 0: Last turn. Accept > 0.
            
            # This logic implies second player gets crushed.
            # But we must maximize OUR deal.
            # Maybe the opponent is not perfectly rational or is willing to split.
            # We shouldn't demand Total if it causes rejection and 0 profit.
            # We should demand the maximum that is likely to be accepted.
            
            # Revised Competitive Threshold:
            # Just try to get Fair Share or slightly more to leverage position, but clamp at Total.
            # If I am last (Me=1) and it's my turn to respond, and no rounds left, accept > 0.
            if is_last_offer:
                target_share = 1 # Accept anything non-zero
            else:
                # In intermediate rounds, try to hold out for fair share or better.
                target_share = fair_share

        # Ensure we don't accept less than 0
        return max(target_share, 0)

    def generate_offer(self) -> list[int]:
        """
        Generates a proposal that maximizes our value.
        """
        # Ideally we want everything.
        # But we need to be realistic to avoid impasse if opponent is rational/learning.
        # However, the prompt says "maximize the value of your deal" and the leaderboard
        # suggests aggressive agents win. 
        # Also, we don't know opponent's values, so we can't optimize Pareto efficiency.
        # We assume we need to offer a deal that the opponent *might* accept.
        # The only thing we know is the opponent's total value is same as ours.
        # We don't know distribution. 
        # Offering 50% of total mass (items) is a safe heuristic for a "fair" split that 
        # might be accepted, but we prefer to keep our high-value items.
        
        # Strategy:
        # 1. Try to take all items with non-zero value.
        #    This gives us max value.
        #    If opponent values these items 0, they accept.
        #    If opponent values them high, they reject.
        # 2. If we are in a "weak" position (Me=1, many rounds left), offering EVERYTHING (Total) 
        #    usually leads to rejection because Opponent (Me=0) expects to get Total eventually.
        #    Actually, if I offer Total to Opponent (i.e., I take 0), they accept.
        #    But I want Max value.
        
        # Let's refine based on "Aggressive" strategy that fits the constraints:
        # Just take what is valuable to us.
        my_offer = [0] * self.num_items
        for i in range(self.num_items):
            if self.values[i] > 0:
                my_offer[i] = self.counts[i]
            else:
                my_offer[i] = 0
                
        return my_offer