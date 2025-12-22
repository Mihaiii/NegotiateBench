class Agent:
    def __init__(self, me, counts, values, max_rounds):
        self.me = me
        self.counts = counts
        self.values = values
        self.rounds = max_rounds
        self.total = sum(c * v for c, v in zip(counts, values))
        self.opponent_wants = [0, 0, 0]

    def offer(self, o):
        self.rounds -= 1
        if o:
            total_sum = sum(self.values[i] * o[i] for i in range(len(o)))
            if self.rounds == 0 and self.me == 1 and total_sum > 0:
                return None
            if total_sum > 9:
                return None
            for i in range(len(o)):
                self.opponent_wants[i] += self.counts[i] - o[i]
            max_val = -1
            index = -1
            for i in range(len(o)):
                if self.values[i] > 8:
                    continue
                w = self.opponent_wants[i] / self.counts[i]
                if w == max_val:
                    if self.values[i] < self.values[index]:
                        max_val = w
                        index = i
                elif w > max_val:
                    max_val = w
                    index = i

            o = self.counts.copy()
            flag = False
            for i in range(len(o)):
                if self.values[i] == 0:
                    o[i] = 0
                    flag = True
            if (not flag or self.rounds == 0) and index >= 0 and o[index] > 0:
                o[index] -= 1
            return o
        else:
            return self.counts.copy()
