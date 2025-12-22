class Agent:
    def __init__(self, me, counts, values, max_rounds):
        self.me = me
        self.counts = counts
        self.values = values
        self.max_rounds = max_rounds
        self.last_offer = None
        self.turn = 0  # Track the number of turns elapsed

    def offer(self, o):
        self.turn += 1
        if o is None:
            # Make initial offer based on heuristic
            my_offer = []
            for i in range(len(self.counts)):
                if self.values[i] > 0:
                    if self.counts[i] == 1:
                        my_offer.append(1)
                    else:
                        my_offer.append(self.counts[i] - 1)
                else:
                    my_offer.append(0)
            self.last_offer = my_offer
            return my_offer
        else:
            # Evaluate the opponent's offer
            my_val = 0
            for i in range(len(o)):
                my_val += o[i] * self.values[i]
            my_total = 0
            for i in range(len(self.counts)):
                my_total += self.counts[i] * self.values[i]
            
            # Accept if no value, or if value meets threshold or it's the last turn
            if my_total == 0 or my_val >= 0.5 * my_total or self.turn >= 2 * self.max_rounds - 1:
                return None
            
            # Generate or adjust a counter offer
            if self.last_offer is not None:
                new_offer = list(self.last_offer)
                # Find the item with the smallest value to reduce
                min_val = float('inf')
                min_idx = -1
                for i in range(len(new_offer)):
                    if new_offer[i] > 0 and self.values[i] < min_val:
                        min_val = self.values[i]
                        min_idx = i
                if min_idx != -1 and new_offer[min_idx] > 0:
                    new_offer[min_idx] -= 1
                self.last_offer = new_offer
                return new_offer
            else:
                # First counter offer, use heuristic
                my_offer = []
                for i in range(len(self.counts)):
                    if self.values[i] > 0:
                        if self.counts[i] == 1:
                            my_offer.append(1)
                        else:
                            my_offer.append(self.counts[i] - 1)
                    else:
                        my_offer.append(0)
                self.last_offer = my_offer
                return my_offer
        return None