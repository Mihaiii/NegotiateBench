import math
import random
import time

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        # Store basic parameters
        self.me = me
        self.counts = counts.copy()
        self.values = values.copy()
        self.max_rounds = max_rounds
        self.round = 0
        
        # Calculate total value and my valuations
        self.total_value = sum(counts[i] * values[i] for i in range(len(counts)))
        
        # Generate all possible splits (reduced set for efficiency)
        self.generate_possible_splits()
        
        # Track opponent's revealed preferences
        self.opponent_rejected = []
        self.opponent_accepted = []
        
        # Target value based on round - becomes more conciliatory over time
        self.target_ratio = 0.8  # Start high
        
        # Cache for efficiency
        self.best_splits_by_value = {}
        self.sort_splits_by_my_value()
    
    def generate_possible_splits(self):
        """Generate a reasonable subset of all possible splits for efficiency."""
        self.all_splits = []
        n_types = len(self.counts)
        
        # Generate using DFS with pruning
        def dfs(current, idx):
            if idx == n_types:
                # Ensure we don't exceed counts
                valid = True
                for i in range(n_types):
                    if current[i] > self.counts[i]:
                        valid = False
                        break
                if valid:
                    self.all_splits.append(current.copy())
                return
            
            # Try reasonable numbers of this item type
            max_items = min(self.counts[idx], 3)  # Limit to 3 of each type for efficiency
            for i in range(max_items + 1):
                current.append(i)
                dfs(current, idx + 1)
                current.pop()
        
        dfs([], 0)
    
    def sort_splits_by_my_value(self):
        """Sort splits by my value and cache them."""
        split_values = []
        for split in self.all_splits:
            my_value = sum(split[i] * self.values[i] for i in range(len(split)))
            split_values.append((my_value, split))
        
        # Sort descending by my value
        split_values.sort(reverse=True, key=lambda x: x[0])
        self.sorted_splits = [split for _, split in split_values]
        
        # Group by value for quick lookup
        for value, split in split_values:
            if value not in self.best_splits_by_value:
                self.best_splits_by_value[value] = split
    
    def calculate_my_value(self, offer):
        """Calculate how much an offer is worth to me."""
        if offer is None:
            return 0
        return sum(offer[i] * self.values[i] for i in range(len(offer)))
    
    def is_valid_offer(self, offer):
        """Check if an offer is valid (doesn't exceed available items)."""
        if offer is None:
            return False
        for i in range(len(offer)):
            if offer[i] < 0 or offer[i] > self.counts[i]:
                return False
        return True
    
    def find_counter_offer(self, opponent_offer):
        """Find a good counter-offer based on current strategy."""
        self.round += 1
        
        # Calculate how desperate we should be based on remaining rounds
        rounds_left = self.max_rounds - (self.round // 2)
        if rounds_left <= 0:
            # Last chance - accept if we get anything
            if opponent_offer and self.calculate_my_value(opponent_offer) > 0:
                return None
        
        # Adjust target ratio based on round - become more flexible over time
        time_pressure = 1.0 - (self.round / (self.max_rounds * 2))
        current_target = max(0.5, self.target_ratio * time_pressure)
        
        # If opponent made an offer, evaluate it
        if opponent_offer:
            my_value = self.calculate_my_value(opponent_offer)
            
            # Accept if offer meets our current target
            if my_value >= current_target * self.total_value:
                return None
            
            # If opponent's offer gives us nothing, definitely counter
            if my_value == 0:
                return self.find_best_counter_offer(current_target)
        
        # Find a counter offer
        return self.find_best_counter_offer(current_target)
    
    def find_best_counter_offer(self, target_ratio):
        """Find the best counter offer that meets our target."""
        target_value = target_ratio * self.total_value
        
        # First try to find an exact match
        for split in self.sorted_splits:
            my_value = self.calculate_my_value(split)
            if my_value >= target_value:
                # Check if this gives opponent something (not all zeros for us)
                opponent_gets_something = False
                for i in range(len(split)):
                    if split[i] < self.counts[i]:
                        opponent_gets_something = True
                        break
                
                if opponent_gets_something:
                    return split
        
        # If no exact match, find the best we can do
        if self.sorted_splits:
            return self.sorted_splits[0]
        
        # Fallback: ask for everything valuable to us
        fallback = []
        for i in range(len(self.counts)):
            if self.values[i] > 0:
                fallback.append(self.counts[i])
            else:
                fallback.append(0)
        return fallback
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        """Main offer method - called on each turn."""
        # First move if we're first
        if self.me == 0 and o is None and self.round == 0:
            self.round = 1
            # Start with a strong but reasonable offer
            return self.find_best_counter_offer(0.7)
        
        # Otherwise, respond to opponent's offer
        return self.find_counter_offer(o)