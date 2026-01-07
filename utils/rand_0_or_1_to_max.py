import random

def rand_0_or_1_to_max(max_value):
    if max_value <= 0:
        return 0
    return random.randint(1, max_value)
