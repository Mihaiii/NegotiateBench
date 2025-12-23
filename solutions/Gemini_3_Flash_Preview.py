class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.total_turns = max_rounds * 2
        self.current_turn = 0
        self.total_value = sum(c * v for c, v in zip(counts, values))
        
        # Priority for items based on our valuation
        self.items_by_value = sorted(range(len(counts)), key=lambda i: values[i], reverse=True)

    def offer(self, o: list[int] | None) -> list[int] | None:
        self.current_turn += 1 if o is None else 2
        
        # Calculate utility of the offer received
        received_val = sum(o[i] * self.values[i] for i in range(len(o))) if o is not None else 0
        
        # Progress from 0 to 1
        progress = self.current_turn / self.total_turns

        # 1. Acceptance Logic
        if o is not None:
            # Last second desperation: if we are player 1 and this is the final opportunity
            if self.me == 1 and self.current_turn >= self.total_turns:
                 if received_val > 0:
                     return None
            
            # Dynamic thresholding
            if progress < 0.3:
                threshold = 0.9 * self.total_value
            elif progress < 0.6:
                threshold = 0.75 * self.total_value
            elif progress < 0.85:
                threshold = 0.6 * self.total_value
            else:
                threshold = 0.5 * self.total_value
            
            # If the offer is good enough, accept
            if received_val >= max(threshold, 1):
                return None

        # 2. Counter-offer Logic
        # Determine how much we are willing to concede
        if progress < 0.2:
            target_ratio = 1.0
        elif progress < 0.5:
            target_ratio = 0.9
        elif progress < 0.8:
            target_ratio = 0.8
        elif progress < 0.95:
            target_ratio = 0.7
        else:
            target_ratio = 0.6
            
        return self._create_offer(target_ratio)

    def _create_offer(self, ratio: float) -> list[int]:
        target_val = ratio * self.total_value
        my_offer = [0] * len(self.counts)
        current_val = 0
        
        # Fill the most valuable items first (Greedy)
        for i in self.items_by_value:
            for _ in range(self.counts[i]):
                if current_val + self.values[i] <= target_val:
                    my_offer[i] += 1
                    current_val += self.values[i]
                else:
                    break
                    
        # Ensure we always offer something valid if target_val is low
        if current_val == 0 and self.total_value > 0:
            for i in self.items_by_value:
                if self.values[i] > 0:
                    my_offer[i] = 1
                    break
        
        # To avoid being perceived as greedy/stagnant (like the history examples), 
        # ensure we give away items with 0 value to us if the partner might want them.
        for i in range(len(self.counts)):
            if self.values[i] == 0:
                # If it's early/mid game, give them all the items that are worthless to us
                # to signal cooperation.
                my_offer[i] = 0 
                
        # If we are demanding everything, and it's not the first turn, concede one small item
        if sum(my_offer) == sum(self.counts) and self.current_turn > 1:
            for i in reversed(self.items_by_value):
                if my_offer[i] > 0:
                    my_offer[i] -= 1
                    break
                    
        return my_offer