import re

greedyness = 100500

def to_str(a):
    return ''.join(format(x, 'x') for x in a)

def to_arr(s):
    return [int(c, 16) for c in s]

def strict_subset(a, b):
    a1 = list(a)
    a2 = list(b)
    ok = False
    for i in range(3):
        if a1[i] > a2[i]:
            return False
        if a1[i] < a2[i]:
            ok = True
    return ok

def things(i):
    return sum(to_arr(i))

avail_offers = {
    '111': ['001', '010', '011', '100', '101', '110'],
    '112': ['001', '002', '010', '011', '012', '100', '101', '102', '110', '111'],
    '113': ['001', '002', '003', '010', '011', '012', '013', '100', '101', '102', '103', '110', '111', '112'],
    '114': ['001', '002', '003', '004', '010', '011', '012', '013', '014', '100', '101', '102', '103', '104', '110', '111', '112', '113'],
    '121': ['001', '010', '011', '020', '021', '100', '101', '110', '111', '120'],
    '122': ['001', '002', '010', '011', '012', '020', '021', '022', '100', '101', '102', '110', '111', '112', '120', '121'],
    '123': ['001', '002', '003', '010', '011', '012', '013', '020', '021', '022', '023', '100', '101', '102', '103', '110', '111', '112', '113', '120', '121', '122'],
    '131': ['001', '010', '011', '020', '021', '030', '031', '100', '101', '110', '111', '120', '121', '130'],
    '132': ['001', '002', '010', '011', '012', '020', '021', '022', '030', '031', '032', '100', '101', '102', '110', '111', '112', '120', '121', '122', '130', '131'],
    '141': ['001', '010', '011', '020', '021', '030', '031', '040', '041', '100', '101', '110', '111', '120', '121', '130', '131', '140'],
    '211': ['001', '010', '011', '100', '101', '110', '111', '200', '201', '210'],
    '212': ['001', '002', '010', '011', '012', '100', '101', '102', '110', '111', '112', '200', '201', '202', '210', '211'],
    '213': ['001', '002', '003', '010', '011', '012', '013', '100', '101', '102', '103', '110', '111', '112', '113', '200', '201', '202', '203', '210', '211', '212'],
    '221': ['001', '010', '011', '020', '021', '100', '101', '110', '111', '120', '121', '200', '201', '210', '211', '220'],
    '222': ['001', '002', '010', '011', '012', '020', '021', '022', '100', '101', '102', '110', '111', '112', '120', '121', '122', '200', '201', '202', '210', '211', '212', '220', '221'],
    '231': ['001', '010', '011', '020', '021', '030', '031', '100', '101', '110', '111', '120', '121', '130', '131', '200', '201', '210', '211', '220', '221', '230'],
    '311': ['001', '010', '011', '100', '101', '110', '111', '200', '201', '210', '211', '300', '301', '310'],
    '312': ['001', '002', '010', '011', '012', '100', '101', '102', '110', '111', '112', '200', '201', '202', '210', '211', '212', '300', '301', '302', '310', '311'],
    '321': ['001', '010', '011', '020', '021', '100', '101', '110', '111', '120', '121', '200', '201', '210', '211', '220', '221', '300', '301', '310', '311', '320'],
    '411': ['001', '010', '011', '100', '101', '110', '111', '200', '201', '210', '211', '300', '301', '310', '311', '400', '401', '410'],
}

avail_valuations = {
    '111': ['00a', '019', '028', '037', '046', '055', '064', '073', '082', '091', '0a0', '109', '118', '127', '136', '145', '154', '163', '172', '181', '190', '208', '217', '226', '235', '244', '253', '262', '271', '280', '307', '316', '325', '334', '343', '352', '361', '370', '406', '415', '424', '433', '442', '451', '460', '505', '514', '523', '532', '541', '550', '604', '613', '622', '631', '640', '703', '712', '721', '730', '802', '811', '820', '901', '910', 'a00'],
    '112': ['005', '024', '043', '062', '081', '0a0', '114', '133', '152', '171', '190', '204', '223', '242', '261', '280', '313', '332', '351', '370', '403', '422', '441', '460', '512', '531', '550', '602', '621', '640', '711', '730', '801', '820', '910', 'a00'],
    '113': ['013', '042', '071', '0a0', '103', '132', '161', '190', '222', '251', '280', '312', '341', '370', '402', '431', '460', '521', '550', '611', '640', '701', '730', '820', '910', 'a00'],
    '114': ['022', '061', '0a0', '112', '151', '190', '202', '241', '280', '331', '370', '421', '460', '511', '550', '601', '640', '730', '820', '910', 'a00'],
    '121': ['00a', '018', '026', '034', '042', '050', '109', '117', '125', '133', '141', '208', '216', '224', '232', '240', '307', '315', '323', '331', '406', '414', '422', '430', '505', '513', '521', '604', '612', '620', '703', '711', '802', '810', '901', 'a00'],
    '122': ['005', '014', '023', '032', '041', '050', '204', '213', '222', '231', '240', '403', '412', '421', '430', '602', '611', '620', '801', '810', 'a00'],
    '123': ['022', '050', '103', '131', '212', '240', '321', '402', '430', '511', '620', '701', '810', 'a00'],
    '131': ['00a', '017', '024', '031', '109', '116', '123', '130', '208', '215', '222', '307', '314', '321', '406', '413', '420', '505', '512', '604', '611', '703', '710', '802', '901', 'a00'],
    '132': ['005', '022', '113', '130', '204', '221', '312', '403', '420', '511', '602', '710', '801', 'a00'],
    '141': ['00a', '016', '022', '109', '115', '121', '208', '214', '220', '307', '313', '406', '412', '505', '511', '604', '610', '703', '802', '901', 'a00'],
    '211': ['00a', '019', '028', '037', '046', '055', '064', '073', '082', '091', '0a0', '108', '117', '126', '135', '144', '153', '162', '171', '180', '206', '215', '224', '233', '242', '251', '260', '304', '313', '322', '331', '340', '402', '411', '420', '500'],
    '212': ['005', '024', '043', '062', '081', '0a0', '104', '123', '142', '161', '180', '203', '222', '241', '260', '302', '321', '340', '401', '420', '500'],
    '213': ['013', '042', '071', '0a0', '122', '151', '180', '202', '231', '260', '311', '340', '420', '500'],
    '221': ['00a', '018', '026', '034', '042', '050', '108', '116', '124', '132', '140', '206', '214', '222', '230', '304', '312', '320', '402', '410', '500'],
    '222': ['005', '014', '023', '032', '041', '050', '104', '113', '122', '131', '140', '203', '212', '221', '230', '302', '311', '320', '401', '410', '500'],
    '231': ['00a', '017', '024', '031', '108', '115', '122', '206', '213', '220', '304', '311', '402', '500'],
    '311': ['00a', '019', '028', '037', '046', '055', '064', '073', '082', '091', '0a0', '107', '116', '125', '134', '143', '152', '161', '170', '204', '213', '222', '231', '240', '301', '310'],
    '312': ['005', '024', '043', '062', '081', '0a0', '113', '132', '151', '170', '202', '221', '240', '310'],
    '321': ['00a', '018', '026', '034', '042', '050', '107', '115', '123', '131', '204', '212', '220', '301'],
    '411': ['00a', '019', '028', '037', '046', '055', '064', '073', '082', '091', '0a0', '106', '115', '124', '133', '142', '151', '160', '202', '211', '220'],
}

class Agent:
    def __init__(self, me: int, counts: list[int], values: list[int], max_rounds: int):
        self.me = me
        self.counts = counts
        self.values = values
        self.rounds = max_rounds
        self.total = 0
        
        def value(o):
            arr = to_arr(o)
            return sum(arr[i] * values[i] for i in range(len(arr)))
        
        def value2(o, v):
            arr = to_arr(o)
            val_arr = to_arr(v)
            return sum(val_arr[i] * (counts[i] - arr[i]) for i in range(len(arr)))
        
        self.value = value
        self.value2 = value2
        
        my = to_str(values)
        c = to_str(counts)
        self.vals = [v for v in avail_valuations[c] if v != my]
        self.vals_copy = self.vals.copy()
        self.offers = [o for o in avail_offers[c] if value(o)]
        
        def sort_key(x):
            vals_to_use = self.vals if self.vals else self.vals_copy
            return (-self.value(x), 
                   sum(self.value2(x, v) for v in vals_to_use),
                   -things(x), 
                   x)
        
        self.sort_key = sort_key
        self.offers.sort(key=self.sort_key)
        
        if len(self.offers) > 0:
            self.best_we_can_hope_for = self.value(self.offers[0])
        else:
            self.best_we_can_hope_for = 0
        
        if me:
            if re.search(r'0..', my):
                if re.search(r'00.', my):
                    self.offers = [o for o in self.offers if re.search(r'00.', o)]
                elif re.search(r'0.0', my):
                    self.offers = [o for o in self.offers if re.search(r'0.0', o)]
                else:
                    self.offers = [o for o in self.offers if re.search(r'0..', o)]
            elif re.search(r'.0.', my):
                if re.search(r'.00', my):
                    self.offers = [o for o in self.offers if re.search(r'.00', o)]
                else:
                    self.offers = [o for o in self.offers if re.search(r'.0.', o)]
            elif re.search(r'..0', my):
                self.offers = [o for o in self.offers if re.search(r'..0', o)]
            
            y = 3
            if c == '111':
                y = 1
            elif c == '114' or c == '122':
                y = 5
            elif c == '212' or c == '221':
                y = 2
            self.offers = [o for o in self.offers if self.value(o) > self.best_we_can_hope_for - y]
        elif c == '111':
            self.offers = [o for o in self.offers if self.value(o) > self.best_we_can_hope_for - 2]
        else:
            self.offers = [o for o in self.offers if self.value(o) > self.best_we_can_hope_for - 1]
        
        self.offers_sent = []
        self.offers_received = []
        self.greedyness = 0
    
    def offer(self, o: list[int] | None) -> list[int] | None:
        self.rounds -= 1
        if o is None:
            if len(self.offers) > 0:
                offer_str = self.offers.pop(0)
                self.offers_sent.append(offer_str)
                return to_arr(offer_str)
            else:
                return None
        
        offer_str = to_str(o)
        
        if self.me and not self.rounds:
            if self.value(offer_str):
                return None
            else:
                return self.counts.copy()
        
        if self.value(offer_str) >= self.best_we_can_hope_for:
            return None
        
        if offer_str in self.offers_sent:
            return None
        
        if self.me and self.rounds == 1:
            d = self.best_we_can_hope_for - 4
            c = to_str(self.counts)
            if c == '111':
                d = 7
            elif c == '112' or c == '121' or c == '211':
                d = 6
            elif c == '114' or c == '141':
                d = 5
            received = [offer_str] + self.offers_received
            b = None
            for r in received:
                if self.value(r) < d:
                    continue
                if b is None or self.value(r) > self.value(b):
                    b = r
            if b:
                if b == offer_str:
                    return None
                else:
                    return to_arr(b)
        
        if len(self.offers_sent) > 0:
            l = self.offers_sent[-1]
            self.vals = [v for v in self.vals if self.value2(l, v) != 10]
        
        if (len(self.offers_received) > 0 and len(self.vals) > 0 and 
            offer_str not in self.offers_received and
            not any(strict_subset(offer_str, r) for r in self.offers_received)):
            self.vals = [v for v in self.vals if self.value2(offer_str, v) and 
                        not any(self.value2(r, v) < self.value2(offer_str, v) for r in self.offers_received)]
        
        if len(self.offers_received) == 0:
            z = sum(1 for n in o if n != 0)
            if z == 2:
                if re.search(r'0..', offer_str):
                    if o[1] == self.counts[1] and o[2] == self.counts[2]:
                        self.vals = [v for v in self.vals if re.search(r'.00', v)]
                elif re.search(r'.0.', offer_str):
                    if o[0] == self.counts[0] and o[2] == self.counts[2]:
                        self.vals = [v for v in self.vals if re.search(r'0.0', v)]
                elif re.search(r'..0', offer_str):
                    if o[0] == self.counts[0] and o[1] == self.counts[1]:
                        self.vals = [v for v in self.vals if re.search(r'00.', v)]
            elif z == 1:
                if o[0]:
                    self.vals = [v for v in self.vals if 
                               (lambda a: a[0] <= a[1] and a[0] <= a[2])(to_arr(v))]
                    if o[0] == self.counts[0]:
                        if self.counts[0] > 1:
                            self.vals = [v for v in self.vals if re.search(r'0..', v)]
                elif o[1]:
                    self.vals = [v for v in self.vals if 
                               (lambda a: a[1] <= a[0] and a[1] <= a[2])(to_arr(v))]
                    if o[1] == self.counts[1]:
                        if self.counts[1] > 1:
                            self.vals = [v for v in self.vals if re.search(r'.0.', v)]
                elif o[2]:
                    self.vals = [v for v in self.vals if 
                               (lambda a: a[2] <= a[0] and a[2] <= a[1])(to_arr(v))]
                    if o[2] == self.counts[2]:
                        if self.counts[2] > 1:
                            self.vals = [v for v in self.vals if re.search(r'..0', v)]
        
        if self.value(offer_str) > self.greedyness:
            self.greedyness = self.value(offer_str)
        
        self.offers_received.append(offer_str)
        self.offers = [z for z in self.offers if 
                      z != offer_str and
                      self.value(z) >= self.greedyness and
                      any(self.value2(z, v) for v in self.vals) and
                      not strict_subset(z, offer_str)]
        
        self.offers.sort(key=self.sort_key)
        
        if not self.rounds:
            offers = self.offers_received.copy()
            if len(offers) > 0:
                sorted_offers = sorted(offers, key=self.sort_key)
                oo = sorted_offers[0]
                for x in sorted_offers:
                    v = self.value(x)
                    if v == self.value(oo) and x == offer_str:
                        oo = x
                        break
                    if v < self.value(oo):
                        break
            else:
                oo = None
            
            div_by = 0
            vals = self.vals if self.vals else self.vals_copy
            fq = []
            for i in range(len(vals)):
                p = 0
                for r in self.offers_received:
                    p += self.value2(r, vals[i])
                div_by += p
                fq.append([vals[i], p])
            
            fq.sort(key=lambda a: (-a[1], a[0]))
            for i in range(len(fq)):
                if div_by > 0:
                    fq[i][1] /= div_by
            
            m = self.value(oo) if oo else 0
            my = '000'
            offers = [x for x in avail_offers[to_str(self.counts)] 
                     if x not in self.offers_received]
            myv = 0
            for x in offers:
                if not self.value(x):
                    continue
                sum_val = 0
                for f in fq:
                    v = self.value2(x, f[0])
                    if v:
                        sum_val += (self.value(x) - m) * f[1]
                    else:
                        sum_val -= m * f[1]
                if sum_val > myv or (sum_val == myv and self.value(x) > self.value(my)):
                    myv = sum_val
                    my = x
            
            if oo and self.value(oo) and self.value(oo) >= self.value(my):
                if oo == offer_str:
                    return None
                else:
                    return to_arr(oo)
            if self.value(my):
                return to_arr(my)
            elif len(self.offers_sent) > 0:
                return to_arr(self.offers_sent[0])
            else:
                return None
        
        offer_this = None
        if len(self.offers) > 0:
            offer_this = self.offers.pop(0)
        elif len(self.offers_sent) > 0:
            offer_this = self.offers_sent[0]
        else:
            c = self.counts.copy()
            for i in range(len(c)):
                if not self.values[i]:
                    c[i] = 0
            if c[0] and c[1] and c[2]:
                min_val = 10
                mini = 0
                for i in range(len(self.values)):
                    if self.values[i] < min_val:
                        min_val = self.values[i]
                        mini = i
                c[mini] -= 1
            offer_this = to_str(c)
            offers = self.offers_received.copy()
            if len(offers) > 0:
                sorted_offers = sorted(offers, key=self.sort_key)
                if self.value(sorted_offers[0]) >= self.value(offer_this):
                    offer_this = sorted_offers[0]
        
        self.offers_sent.append(offer_this)
        if offer_this == offer_str:
            return None
        else:
            return to_arr(offer_this)

