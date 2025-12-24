est_error_multiplier = 0.6


def value_counts(agent, counts):
    return sum(agent.items[i]["value"] * counts[i] for i in range(len(agent.items)))


def make_offer_of_undesirables(agent, no_value_offer_count):
    agent.no_value_offer_count = no_value_offer_count
    offered_count_sum = 0
    result = []
    for item in agent.items:
        count = item["count"]
        value = item["value"]
        if value:
            result.append(count)
        else:
            offered_count = 0
            if offered_count_sum < no_value_offer_count:
                offered_count = min(no_value_offer_count - offered_count_sum, count)
            offered_count_sum += offered_count
            result.append(count - offered_count)
    return result


class Agent:
    def __init__(self, is_not_first, counts, values, rounds, log=None):
        self.no_value_offer_count = 0
        is_first = self.is_first = not is_not_first
        self.rounds = rounds
        self.rounds_left = rounds
        self.rounds_to_hold = 0
        self.rounds_till_fold = int(rounds * 0.2) + (1 if is_first else 0)
        self.rounds_till_panic = int(rounds * 0.4) + (1 if is_first else 0)
        turns = self.turns = rounds * 2
        items = self.items = []
        total_value = 0
        total_count = 0
        total_no_value_count = 0
        hold_request_counts = self.hold_request_counts = []
        for i in range(len(counts)):
            count = counts[i]
            value = values[i]
            sub_total_value = count * value
            hold_request_counts.append(count)
            items.append(
                {
                    "count": count,
                    "value": value,
                    "sub_total_value": sub_total_value,
                }
            )
            if not value:
                total_no_value_count += count
            total_count += count
            total_value += sub_total_value
        self.prev_request_counts = hold_request_counts
        self.prev_request_value = total_value
        self.opponent_info = {
            "request_history": [],
            "fold_req_history": [],
            "times_held": 0,
            "times_held_after_fold": 0,
            "has_folded": False,
            "is_stubborn": True,
            "sub_total_req_counts": [0] * len(items),
            "total_req_count": 0,
            "importance_scores": [
                items[i]["count"] / total_count for i in range(len(items))
            ],
        }
        self.is_all_valued = not total_no_value_count
        self.total_no_value_count = total_no_value_count
        self.total_value = total_value
        self.total_count = total_count
        self.stubborn_acceptable_offer_value = total_value / 2
        self.lowest_req_value = total_value * 0.7

    def offer(self, offered_counts):
        self.rounds_left -= 1
        rounds = self.rounds
        turns = self.turns
        rounds_left = self.rounds_left
        is_first = self.is_first
        prev_request_counts = self.prev_request_counts
        round_num = rounds - rounds_left
        turn = (round_num * 2) - (1 if is_first else 0)
        turns_left = (rounds_left * 2) + (1 if is_first else 0)
        if not offered_counts:
            return self.hold_request_counts
        if prev_request_counts and all(
            prev_request_counts[i] == offered_counts[i]
            for i in range(len(prev_request_counts))
        ):
            return
        opponent_info = self.opponent_info
        total_no_value_count = self.total_no_value_count
        total_count = self.total_count
        total_value = self.total_value
        items = self.items
        prev_offered_counts = getattr(self, "prev_offered_counts", None)
        offer_value = value_counts(self, offered_counts)
        if not turns_left and offer_value:
            return
        if round_num >= self.rounds_till_fold and offer_value == total_value:
            return
        op_requested_counts = [
            items[i]["count"] - offered_counts[i] for i in range(len(items))
        ]
        request_counts = None
        opponent_info["request_history"].append(op_requested_counts)
        if (
            prev_offered_counts
            and opponent_info["is_stubborn"]
            and any(
                offered_counts[i] != prev_offered_counts[i]
                for i in range(len(offered_counts))
            )
        ):
            opponent_info["is_stubborn"] = False
        self.prev_offered_counts = offered_counts
        if all(c == 0 for c in offered_counts):
            opponent_info["times_held"] += 1
            if opponent_info["has_folded"]:
                opponent_info["times_held_after_fold"] += 1
            else:
                no_value_offer_count = self.no_value_offer_count
                if round_num < self.rounds_to_hold:
                    request_counts = self.hold_request_counts
                elif (
                    total_no_value_count and no_value_offer_count < total_no_value_count
                ):
                    if round_num < self.rounds_till_fold:
                        request_counts = make_offer_of_undesirables(
                            self, no_value_offer_count + 1
                        )
                    elif round_num < self.rounds_till_panic:
                        request_counts = make_offer_of_undesirables(
                            self, total_no_value_count
                        )
        else:
            opponent_info["has_folded"] = True
            opponent_info["fold_req_history"].append(op_requested_counts)
        total_req_count = 0
        op_sub_total_counts = []
        for i in range(len(opponent_info["sub_total_req_counts"])):
            sub_total_count = (
                opponent_info["sub_total_req_counts"][i] + op_requested_counts[i]
            )
            total_req_count += sub_total_count
            op_sub_total_counts.append(sub_total_count)
        opponent_info["sub_total_req_counts"] = op_sub_total_counts
        opponent_info["total_req_count"] = total_req_count
        opponent_info["importance_scores"] = [
            op_sub_total_counts[i] / items[i]["count"] for i in range(len(items))
        ]
        if not request_counts:
            importance_scores = opponent_info["importance_scores"]
            important_indexed_items = []
            important_total_value = 0
            important_counts = 0
            no_value_important_count = 0
            for i in range(len(op_sub_total_counts)):
                req_count = op_sub_total_counts[i]
                count = items[i]["count"]
                value = items[i]["value"]
                sub_total_value = items[i]["sub_total_value"]
                if req_count:
                    sub_total_importance = req_count / total_req_count
                    importance = req_count / count
                    est_op_sub_total_value = (
                        importance * total_value * est_error_multiplier
                    )
                    est_op_value = est_op_sub_total_value / count
                    tradability = est_op_value / value if value else 0
                    important_indexed_items.append(
                        {
                            "index": i,
                            "importance": importance,
                            "sub_total_importance": sub_total_importance,
                            "est_op_value": est_op_value,
                            "est_op_sub_total_value": est_op_sub_total_value,
                            "tradability": tradability,
                            "value": value,
                            "count": count,
                            "sub_total_value": sub_total_value,
                        }
                    )
                    important_counts += count
                    important_total_value += sub_total_value
                    if not value and importance_scores[i] > 0.3 * rounds:
                        no_value_important_count += count
            if (
                round_num < self.rounds_till_fold
                and self.no_value_offer_count >= no_value_important_count
            ):
                self.rounds_till_fold = round_num
            if not rounds_left:
                important_indexed_items.sort(key=lambda x: -x["tradability"])
                if opponent_info["is_stubborn"]:
                    stubborn_acceptable_offer_value = (
                        self.stubborn_acceptable_offer_value
                    )
                    offer_counts_map = {}
                    estimated_opposition_total_value = 0
                    req_total_value = total_value
                    for item in important_indexed_items:
                        index = item["index"]
                        count = item["count"]
                        est_op_value = item["est_op_value"]
                        value = item["value"]
                        est_offer_op_value = estimated_opposition_total_value
                        offer_count = 0
                        possible_req_total_value = req_total_value
                        while (
                            est_offer_op_value < stubborn_acceptable_offer_value
                            and offer_count < count
                            and possible_req_total_value - value > 0
                        ):
                            offer_count += 1
                            est_offer_op_value += est_op_value
                            possible_req_total_value -= value
                        offer_counts_map[index] = offer_count
                        estimated_opposition_total_value = est_offer_op_value
                        req_total_value = possible_req_total_value
                        if est_offer_op_value >= stubborn_acceptable_offer_value:
                            break
                    request_counts = []
                    for i in range(len(items)):
                        value = items[i]["value"]
                        count = items[i]["count"]
                        if not value:
                            request_counts.append(0)
                        else:
                            offer_count = offer_counts_map.get(i, 0)
                            request_counts.append(count - offer_count)
                elif no_value_important_count > 0:
                    request_counts = make_offer_of_undesirables(
                        self, self.total_no_value_count
                    )
                else:
                    item_to_offer = important_indexed_items[0]
                    for item in important_indexed_items:
                        if (
                            item["value"]
                            and item["tradability"] > item_to_offer["tradability"]
                        ):
                            item_to_offer = item
                    request_counts = []
                    for i in range(len(items)):
                        count = items[i]["count"]
                        value = items[i]["value"]
                        if not value:
                            request_counts.append(0)
                        elif item_to_offer["index"] == i:
                            request_counts.append(count - 1)
                        else:
                            request_counts.append(count)
            elif round_num < self.rounds_till_fold:
                request_counts = make_offer_of_undesirables(
                    self, self.no_value_offer_count + 1
                )
            else:
                important_indexed_items.sort(key=lambda x: -x["tradability"])
                lowest_req_value = self.lowest_req_value
                low_req_value_delta = total_value - lowest_req_value
                req_value = lowest_req_value + (
                    (rounds_left / (rounds - 1)) * low_req_value_delta
                )
                offer_counts_map = {}
                estimated_opposition_total_value = 0
                req_total_value = total_value
                for item in important_indexed_items:
                    index = item["index"]
                    count = item["count"]
                    est_op_value = item["est_op_value"]
                    value = item["value"]
                    est_offer_op_value = estimated_opposition_total_value
                    offer_count = 0
                    possible_req_total_value = req_total_value
                    while (
                        offer_count < count
                        and possible_req_total_value - value > req_value
                    ):
                        offer_count += 1
                        est_offer_op_value += est_op_value
                        possible_req_total_value -= value
                    offer_counts_map[index] = offer_count
                    estimated_opposition_total_value = est_offer_op_value
                    req_total_value = possible_req_total_value
                request_counts = []
                for i in range(len(items)):
                    value = items[i]["value"]
                    count = items[i]["count"]
                    if not value:
                        request_counts.append(0)
                    else:
                        offer_count = offer_counts_map.get(i, 0)
                        request_counts.append(count - offer_count)
        if request_counts:
            request_value = value_counts(self, request_counts)
            if offer_value > request_value and not rounds_left:
                return
            self.prev_request_counts = request_counts
            self.prev_request_value = request_value
            return request_counts
