import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.turns_played = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Flatten the inventory into individual items (value, index)
        # This simplifies the logic to a greedy selection of individual units
        self.all_items = []
        for idx, count in enumerate(counts):
            for _ in range(count):
                self.all_items.append((values[idx], idx))
        
        # Sort items by value descending to prioritize high-value items
        # Shuffle first to introduce randomness in tie-breaking, 
        # avoiding deterministic loops in negotiation
        random.shuffle(self.all_items)
        self.all_items.sort(key=lambda x: x[0], reverse=True)

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turns_played += 1
        remaining_turns = self.max_rounds - self.turns_played
        
        # Calculate the value of the offer provided by the opponent
        offer_val = 0
        if o is not None:
            offer_val = sum(o[i] * self.values[i] for i in range(len(o)))
            
        # Calculate negotiation progress (0.0 to ~1.0)
        # Used to decay the aspiration level
        t = (self.turns_played - 1) / self.max_rounds if self.max_rounds > 0 else 1.0
        
        # Strategy Parameters
        # start_frac: Initial target (percentage of total value)
        # end_frac: Target at the final round
        start_frac = 1.0
        
        # If I am Player 0 (First Mover), my last turn is the second-to-last in the game.
        # The opponent has the final say (Accept/Reject/Counter=Reject).
        # Thus, on my last turn, I must offer a deal they are very likely to accept (Fair split).
        if self.me == 0 and remaining_turns == 0:
            end_frac = 0.5
        else:
            # If I am Player 1 (Second Mover), I have the final say on the very last turn.
            # I can afford to be tougher, but should ensure I don't get 0.
            end_frac = 0.6

        # Determine target using a convex curve (holds high value longer, then drops)
        current_frac = start_frac - (start_frac - end_frac) * (t ** 2)
        target_val = int(self.total_value * current_frac)
        
        # --- Decision Logic ---
        
        if o is not None:
            # 1. Panic Acceptance (Player 1, Last Turn)
            # If I reject/counter now, the game ends with no deal. 
            # Accepting anything > 0 is rational compared to getting 0.
            if self.me == 1 and remaining_turns == 0:
                if offer_val > 0:
                    return None
            
            # 2. Standard Acceptance
            if offer_val >= target_val:
                return None
                
        # --- Generate Counter-Offer ---
        
        # We construct an offer that gives us >= target_val.
        # We use a greedy approach: take items we value most.
        # Ideally, this leaves items we value less (but opponent might value more) to them.
        
        my_proposal = [0] * len(self.counts)
        current_sum = 0
        
        # Ensure we ask for at least something if total value exists
        ask_target = max(1, target_val) if self.total_value > 0 else 0
        
        for val, idx in self.all_items:
            # Stop if we have reached our target value
            if current_sum >= ask_target:
                break
            
            # Add item to our proposal if available
            if my_proposal[idx] < self.counts[idx]:
                my_proposal[idx] += 1
                current_sum += val
                
        return my_proposal