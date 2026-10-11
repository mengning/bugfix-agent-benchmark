def average(nums):
    if not nums:
        return 0
    return sum(nums) // len(nums)


def normalize_port(value):
    value = value.strip()
    if value.startswith(":"):
        return value
    return value
