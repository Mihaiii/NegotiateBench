import math

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.max_turns = max_rounds * 2
        self.turn_count = 0
        
        # Calculate total value and average value per item
        self.total_items = sum(counts)
        self.total_value = sum(c * v for c, v in zip(counts, values))
        self.avg_item_value = self.total_value / self.total_items if self.total_items > 0 else 0
        
        # Strategy parameters
        self.initial_share = 0.55  # Aim for 55% of total value initially
        self.min_share = 0.50      # Settle for 50% at the end
        
    def get_value(self, offer: list[int]) -> int:
        return sum(o * v for o, v in zip(offer, self.values))
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.turn_count += 1
        turns_remaining = self.max_turns - self.turn_count
        
        # 1. Evaluation of Partner's Offer
        if o is not None:
            offer_val = self.get_value(o)
            
            # Acceptance Threshold Logic
            # As we run out of turns, we lower our expectations
            # Linear interpolation from initial_share to min_share
            progress = 1 - (turns_remaining / self.max_turns)
            current_threshold_ratio = self.initial_share * (1 - progress) + self.min_share * progress
            
            min_acceptable = int(self.total_value * current_threshold_ratio)
            
            # Last turn rule: If it's the last turn and offer > 0, accept to avoid 0.
            if turns_remaining == 0:
                if offer_val > 0:
                    return None
            else:
                # Standard acceptance check
                if offer_val >= min_acceptable:
                    return None

        # 2. Construct Counter-Offer (or First Offer)
        
        # Calculate target value for this turn
        progress = 1 - (turns_remaining / self.max_turns)
        target_ratio = self.initial_share * (1 - progress) + self.min_share * progress
        target_val = int(self.total_value * target_ratio)
        
        # Strategy: Proportional Split
        # Instead of taking all high-value items, we take a proportional share of them.
        # This reduces conflict over specific items that both parties value.
        
        offer = [0] * len(self.counts)
        current_val = 0
        
        # Separate items into High Value (above avg) and Low Value (below avg)
        # We aim to satisfy the target primarily using High Value items.
        # This allows us to give away Low Value items (which we value less) 
        # and share High Value items.
        
        high_value_indices = []
        high_value_total = 0
        
        for i in range(len(self.counts)):
            if self.values[i] > self.avg_item_value:
                high_value_indices.append(i)
                high_value_total += self.counts[i] * self.values[i]
        
        # If we can reach target using just a portion of high value items
        if high_value_total >= target_val:
            # Calculate ratio of high value items to take
            ratio = target_val / high_value_total
            
            # Distribute proportional share of high value items
            for i in high_value_indices:
                # Calculate how many of this item to take
                take_float = self.counts[i] * ratio
                take_int = int(take_float)
                
                offer[i] = take_int
                current_val += take_int * self.values[i]
            
            # Due to integer truncation, we might be slightly under target.
            # Add the remaining value from the best remaining high value items.
            deficit = target_val - current_val
            # Sort high value items by value to fill deficit efficiently
            sorted_high = sorted(high_value_indices, key=lambda i: self.values[i], reverse=True)
            
            for i in sorted_high:
                if deficit <= 0:
                    break
                # Can we take more of item i?
                available = self.counts[i] - offer[i]
                if available > 0:
                    val_needed = deficit
                    count_needed = math.ceil(val_needed / self.values[i])
                    take_extra = min(count_needed, available)
                    offer[i] += take_extra
                    deficit -= take_extra * self.values[i]
        
        else:
            # We need some low value items too
            # Take all high value items
            for i in high_value_indices:
                offer[i] = self.counts[i]
                current_val += self.counts[i] * self.values[i]
            
            # Fill remaining with low value items (greedy)
            remaining = target_val - current_val
            low_indices = [i for i in range(len(self.counts)) if i not in high_value_indices]
            sorted_low = sorted(low_indices, key=lambda i: self.values[i], reverse=True)
            
            for i in sorted_low:
                if remaining <= 0:
                    break
                val_per_item = self.values[i]
                if val_per_item == 0:
                    continue
                    
                max_take = self.counts[i]
                if val_per_item * max_take <= remaining:
                    offer[i] = max_take
                    remaining -= val_per_item * max_take
                else:
                    take = math.ceil(remaining / val_per_item)
                    offer[i] = min(take, max_take)
                    remaining -= offer[i] * val_per_item

        return offer