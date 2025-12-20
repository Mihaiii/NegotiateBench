def give_something_away(
    counts, total, values, o, co, current_give_away_index, skip_index=None
):
    give_away_index = len(counts)
    for i in range(len(co)):
        if (
            values[i]
            and ((o and o[i] < counts[i]) or (not o and counts[i] > 0))
            and co[i] > 0
            and values[i] < total * 0.6
            and i != skip_index
        ):
            if give_away_index == len(counts) or values[give_away_index] > values[i]:
                give_away_index = i
            elif values[give_away_index] == values[i]:
                if (not o and counts[i] < counts[give_away_index]) or (
                    o and o[i] < o[give_away_index]
                ):
                    give_away_index = i
    if give_away_index < len(counts):
        co[give_away_index] -= 1
        return give_away_index
    return current_give_away_index


def sum_values(int_co, values):
    total_int_co = 0
    for i in range(len(int_co)):
        total_int_co += values[i] * int_co[i]
    return total_int_co


def give_away_one(values, co, give_away_index_obj):
    for i in range(len(values)):
        if (
            values[i] == 1
            and co[i] > 0
            and (co[i] < values[i] or not give_away_index_obj["partner"][i])
        ):
            co[i] -= 1
            return


def update_give_away_index(give_away_index_obj, give_away_index_new):
    if give_away_index_new < len(give_away_index_obj["mine"]):
        give_away_index_obj["mine"][give_away_index_new] = True
    give_away_index_obj["give_away_index"] = give_away_index_new


def co_wants_everything(counts, o, co):
    if 0 not in co:
        return True

    for i in range(len(o)):
        o[i] = counts[i] - o[i]

    idx_offer = [i for i, e in enumerate(o) if e == 0]
    idx_cnt_offer = [i for i, e in enumerate(co) if e == 0]

    for i in range(len(idx_cnt_offer)):
        if idx_cnt_offer[i] not in idx_offer:
            return False

    return True


class Agent:
    def __init__(self, me, counts, values, max_rounds):
        self.me = me
        self.counts = counts
        self.total_counts = sum(counts)
        self.values = values
        self.rounds = max_rounds
        self.max_rounds = max_rounds
        self.total = 0
        self.made_offers = {"mine": [], "partner": []}
        self.nr_obj = 0
        self.valid_offer = []
        self.give_away = False
        self.force_him_to_give_away = False
        self.accept_sixty = False
        self.min_on_give_away = 0.5
        self.give_away_index_obj = {
            "mine": [False] * len(counts),
            "partner": [False] * len(counts),
            "give_away_index": None,
        }
        for i in range(len(counts)):
            self.total += counts[i] * values[i]
        self.last_made_offer = counts.copy()

    def offer(self, o):
        self.rounds -= 1
        total_o = 0
        fi = self.values.index(0) if 0 in self.values else -1
        li = (
            len(self.values) - 1 - self.values[::-1].index(0)
            if 0 in self.values
            else -1
        )
        co = self.counts.copy()

        if o:
            for i in range(len(o)):
                total_o += self.values[i] * o[i]

            if self.total == total_o:
                return None

            for i in range(len(co)):
                if not self.values[i]:
                    co[i] = 0
                    self.give_away_index_obj["mine"][i] = True

            for i in range(len(o)):
                if o[i] > 0:
                    self.give_away_index_obj["partner"][i] = True

            if fi != li and self.rounds + 1 == self.max_rounds:
                if (
                    self.counts[fi] < self.counts[fi]
                ):  # Note: this is the same in JS (likely a bug in original)
                    co[fi] += 1
                else:
                    co[li] += 1
                self.last_made_offer = co.copy()
                self.made_offers["mine"].append(str(co))
                self.made_offers["partner"].append(str(o))
                return co

            if (
                (self.rounds + 1 == self.max_rounds and self.me)
                or (self.rounds + 2 == self.max_rounds and not self.me)
            ) and total_o >= self.total * 0.8:
                self.force_him_to_give_away = True

            if self.force_him_to_give_away and self.rounds != 0 and 0 in co:
                self.last_made_offer = co.copy()
                self.made_offers["mine"].append(str(co))
                self.made_offers["partner"].append(str(o))
                return co

            if self.me and self.rounds == 0 and total_o > 0:
                return None

            if (
                ((self.me and self.rounds == 1) or (not self.me and self.rounds == 0))
                and len(self.made_offers["partner"]) >= 2
                and total_o < self.total * self.min_on_give_away
            ):
                self.made_offers["partner"].append(str(o))
                if (
                    len(set(self.made_offers["partner"][-3:])) == 1
                    and len(set(self.made_offers["mine"][-3:])) == 1
                ):
                    ret_co = self.counts.copy()
                    for m in range(len(ret_co)):
                        if not self.values[m]:
                            ret_co[m] = 0
                            self.give_away_index_obj["mine"][m] = True
                    tot = self.total
                    for h in range(len(self.give_away_index_obj["partner"])):
                        if (
                            self.give_away_index_obj["partner"][h] == False
                            and self.give_away_index_obj["mine"][h] == False
                        ):
                            if (
                                tot - self.values[h]
                                >= self.total * self.min_on_give_away
                            ):
                                ret_co[h] -= 1
                                tot = tot - self.values[h]
                    if tot != self.total:
                        return ret_co
                self.made_offers["partner"].pop()

            if (
                sum(o) < self.nr_obj
                and len(self.made_offers["partner"]) == 2
                and str(o) in self.made_offers["partner"]
            ):
                self.nr_obj = sum(o)
                self.made_offers["partner"].append(str(o))
                if total_o >= self.total * 0.6:
                    if sum_values(self.valid_offer, self.values) < sum_values(
                        o, self.values
                    ):
                        self.valid_offer = o.copy()
                    self.accept_sixty = True
                self.made_offers["mine"].append(str(self.last_made_offer))
                return self.last_made_offer

            self.nr_obj = sum(o)

            if (
                not self.give_away
                and len(self.made_offers["partner"]) >= 2
                and str(o) in self.made_offers["partner"]
            ):
                if (
                    (
                        (self.rounds == 2 and self.me)
                        or (not self.me and self.rounds == 1)
                    )
                    and (self.total_counts - self.nr_obj) <= 3
                    and total_o > 0
                ):
                    if total_o >= self.total * 0.6 and sum_values(
                        self.valid_offer, self.values
                    ) < sum_values(o, self.values):
                        self.valid_offer = o.copy()
                else:
                    if self.valid_offer and self.made_offers["partner"][-1] == str(o):
                        self.accept_sixty = True
                    self.give_away = True

            self.made_offers["partner"].append(str(o))

        co = self.counts.copy()
        for i in range(len(co)):
            if not self.values[i]:
                co[i] = 0
                self.give_away_index_obj["mine"][i] = True

        give_away_index = len(self.counts)
        if not o:
            if 0 not in co:
                give_away_index = give_something_away(
                    self.counts, self.total, self.values, None, co, give_away_index
                )
        elif co_wants_everything(self.counts, o.copy(), co.copy()):
            give_away_index = give_something_away(
                self.counts, self.total, self.values, o, co, give_away_index
            )

        total_co = sum_values(co, self.values)

        if total_o >= total_co:
            return None

        if (
            total_o >= self.total * 0.7
            and self.rounds + 1 != self.max_rounds
            and len(set(self.made_offers["partner"])) > 1
        ):
            g = co.copy()
            give_something_away(
                self.counts, self.total, self.values, o, g, give_away_index
            )
            t = sum_values(g, self.values)
            if t <= total_o and t >= self.total * 0.6:
                return None

        total_int_co = 0

        if (
            o
            and ((self.rounds <= 2 and self.me) or (not self.me and self.rounds <= 1))
            and self.give_away
        ):
            if (
                total_o >= self.total * self.min_on_give_away
                and self.rounds == 0
                and self.me
            ):
                return None
            if total_o >= sum_values(self.last_made_offer, self.values):
                return None
            if (
                sum_values(o, self.values) > sum_values(self.valid_offer, self.values)
                and not self.accept_sixty
            ):
                if total_o >= self.total * self.min_on_give_away:
                    self.valid_offer = o.copy()
                self.accept_sixty = True
            else:
                if self.accept_sixty and self.valid_offer:
                    if sum_values(o, self.values) >= sum_values(
                        self.valid_offer, self.values
                    ):
                        return None
                    self.made_offers["mine"].append(str(self.valid_offer))
                    if not self.me:
                        return self.valid_offer.copy()

            if not (
                self.me
                and self.rounds == 1
                and len(set(self.made_offers["partner"])) > 1
                and (self.total_counts - self.nr_obj) <= 3
            ):
                int_co = self.last_made_offer.copy()
                give_away_index_h = self.give_away_index_obj["give_away_index"]
                give_away_index_h = give_something_away(
                    self.counts, self.total, self.values, o, int_co, give_away_index_h
                )
                total_int_co = sum_values(int_co, self.values)

                if total_int_co >= self.total * self.min_on_give_away:
                    if total_o >= total_int_co:
                        return None
                    if str(self.give_away_index_obj["mine"]) == str(
                        self.give_away_index_obj["partner"]
                    ):
                        i_co = self.last_made_offer.copy()
                        give_away_index_new = give_something_away(
                            self.counts,
                            self.total,
                            self.values,
                            o,
                            i_co,
                            give_away_index_h,
                            give_away_index_h,
                        )
                        total_i_co = sum_values(i_co, self.values)
                        if total_i_co >= self.total * self.min_on_give_away:
                            if total_o >= total_i_co:
                                return None
                            update_give_away_index(
                                self.give_away_index_obj, give_away_index_new
                            )
                            update_give_away_index(
                                self.give_away_index_obj, give_away_index_h
                            )
                            self.last_made_offer = i_co.copy()
                            self.made_offers["mine"].append(str(i_co))
                            return i_co

                    if total_int_co >= self.total * self.min_on_give_away + 1:
                        give_away_one(self.values, int_co, self.give_away_index_obj)
                    update_give_away_index(self.give_away_index_obj, give_away_index_h)
                    self.last_made_offer = int_co.copy()
                    self.made_offers["mine"].append(str(int_co))
                    return int_co
                self.made_offers["mine"].append(str(self.last_made_offer))
                return self.last_made_offer

        if (
            self.rounds == 0
            and not self.me
            and o
            and total_o >= self.total * 0.4
            and len(set(self.made_offers["partner"])) > 3
        ):
            return None

        if (
            self.rounds == 0
            and not self.me
            and o
            and not (
                fi != -1
                and (
                    not self.give_away_index_obj["partner"][fi]
                    or not self.give_away_index_obj["partner"][li]
                )
            )
        ):
            if total_o >= self.total * 0.6:
                return None
            co_int = co.copy()
            give_something_away(
                self.counts, self.total, self.values, o, co, give_away_index
            )

            total_int_co = sum_values(co, self.values)

            if total_int_co >= self.total * 0.6:
                if total_int_co >= self.total * 0.6 + 1:
                    give_away_one(self.values, co, self.give_away_index_obj)
                return co
            return co_int

        update_give_away_index(self.give_away_index_obj, give_away_index)
        self.last_made_offer = co.copy()
        self.made_offers["mine"].append(str(co))
        return co
