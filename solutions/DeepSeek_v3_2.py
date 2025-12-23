import itertools
import random

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts.copy()
        self.values = values.copy()
        self.max_rounds = max_rounds
        
        # Calculate my total value
        self.my_total_value = sum(counts[i] * values[i] for i in range(len(counts)))
        
        # Track turn information
        self.turn = 0
        self.round = 0
        
        # Generate all possible splits using cartesian product
        self.all_splits = []
        ranges = [range(count + 1) for count in counts]
        self.all_splits = list(itertools.product(*ranges))
        
        # Calculate my value for each split
        self.split_values = {}
        for split in self.all_splits:
            my_val = sum(split[i] * values[i] for i in range(len(split)))
            self.split_values[split] = my_val
        
        # Sort splits by my value (descending)
        self.sorted_splits = sorted(self.all_splits, 
                                   key=lambda x: self.split_values[x], 
                                   reverse=True)
        
        # Track opponent behavior
        self.opponent_offers = []
        self.my_offers = []
        self.opponent_rejected = []
        
        # Initialize target value based on round strategy
        self.target_value = self.my_total_value * 0.8
        
        # Estimate opponent values based on their offers
        self.opponent_value_estimates = [0] * len(counts)
        
        # Time pressure factor
        self.time_pressure = 1.0
    
    def calculate_my_value(self, offer):
        """Calculate value of an offer to me."""
        if offer is None:
            return 0
        return sum(offer[i] * self.values[i] for i in range(len(offer)))
    
    def calculate_opponent_value(self, offer, my_share):
        """Estimate opponent's value for what they would get."""
        if offer is None:
            return 0
        
        # What opponent gets = total items - what I get
        opponent_share = []
        for i in range(len(offer)):
            opponent_share.append(self.counts[i] - my_share[i])
        
        # Use our estimates of opponent values
        return sum(opponent_share[i] * self.opponent_value_estimates[i] 
                  for i in range(len(opponent_share)))
    
    def update_opponent_model(self, opponent_offer):
        """Update our model of opponent's preferences based on their offer."""
        if opponent_offer is None or not self.opponent_offers:
            return
        
        # Track all opponent offers
        self.opponent_offers.append(opponent_offer)
        
        # If we have at least 2 offers, try to infer preferences
        if len(self.opponent_offers) >= 2:
            # Compare current and previous offer
            prev_offer = self.opponent_offers[-2]
            
            # What changed?
            for i in range(len(opponent_offer)):
                if opponent_offer[i] > prev_offer[i]:
                    # They increased what they offer me of type i
                    # This suggests they don't value this type highly
                    self.opponent_value_estimates[i] = max(0, self.opponent_value_estimates[i] - 0.1)
                elif opponent_offer[i] < prev_offer[i]:
                    # They decreased what they offer me of type i
                    # This suggests they value this type highly
                    self.opponent_value_estimates[i] = min(10, self.opponent_value_estimates[i] + 0.1)
    
    def generate_counter_offer(self, current_target):
        """Generate a counter-offer that meets our target and is likely acceptable."""
        
        # Calculate time pressure (more flexible as time runs out)
        turns_left = (self.max_rounds * 2) - self.turn
        self.time_pressure = max(0.1, turns_left / (self.max_rounds * 2))
        
        # Adjust target based on time pressure
        adjusted_target = current_target * (0.5 + 0.5 * self.time_pressure)
        
        # First, try to find splits that meet our adjusted target
        candidate_splits = []
        for split in self.sorted_splits:
            my_val = self.split_values[split]
            
            # Check if this gives opponent something reasonable
            opponent_val = self.calculate_opponent_value(split, split)
            
            if my_val >= adjusted_target and opponent_val > 0:
                candidate_splits.append((split, my_val, opponent_val))
        
        # If we found candidates, choose one
        if candidate_splits:
            # Sort by combined score (balancing our and opponent's value)
            candidate_splits.sort(key=lambda x: x[1] * 0.7 + x[2] * 0.3, reverse=True)
            best_split = candidate_splits[0][0]
            return list(best_split)
        
        # If no candidates meet target, find the best we can do
        for split in self.sorted_splits:
            my_val = self.split_values[split]
            opponent_val = self.calculate_opponent_value(split, split)
            
            if opponent_val > 0:
                return list(split)
        
        # Last resort: ask for everything
        return self.counts.copy()
    
    def should_accept(self, opponent_offer, current_target):
        """Determine whether to accept opponent's offer."""
        if opponent_offer is None:
            return False
        
        my_val = self.calculate_my_value(opponent_offer)
        
        # Calculate time pressure
        turns_left = (self.max_rounds * 2) - self.turn
        accept_threshold = current_target * (0.7 + 0.3 * (1 - self.time_pressure))
        
        # Accept if:
        # 1. Offer meets our threshold, OR
        # 2. It's the last turn and we get anything positive
        if my_val >= accept_threshold:
            return True
        
        if turns_left <= 1 and my_val > 0:
            return True
        
        # If opponent consistently offers similar values and we're getting desperate
        if len(self.opponent_offers) >= 2 and turns_left < 3:
            avg_opponent_value = sum(self.calculate_my_value(o) for o in self.opponent_offers[-3:]) / min(3, len(self.opponent_offers))
            if my_val >= avg_opponent_value * 0.9:
                return True
        
        return False
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        """Main offer method."""
        self.turn += 1
        
        # Update opponent model if they made an offer
        if o is not None:
            self.update_opponent_model(o)
        
        # First move if we're first
        if self.me == 0 and self.turn == 1:
            # Start with a reasonable but strong offer
            # Aim for about 70% of total value
            initial_target = self.my_total_value * 0.7
            return self.generate_counter_offer(initial_target)
        
        # Determine if we should accept
        current_target = self.my_total_value * 0.6  # Base target
        
        if self.should_accept(o, current_target):
            return None
        
        # Otherwise, make a counter-offer
        # Adjust target based on how negotiations are going
        if self.opponent_offers:
            # Get average of opponent's offers to me
            avg_opponent_offer = sum(self.calculate_my_value(offer) for offer in self.opponent_offers) / len(self.opponent_offers)
            
            # If opponent has been generous, be more ambitious
            if avg_opponent_offer > self.my_total_value * 0.5:
                current_target = max(current_target, avg_opponent_offer * 0.9)
            else:
                # Opponent is tough, be more flexible
                current_target = current_target * 0.8
        
        return self.generate_counter_offer(current_target)