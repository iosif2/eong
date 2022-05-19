
def divide_messages_for_embed(messages: list):
    msgs = []
    embed_count = 0
    msgs.append('')
    for msg in messages:
        if not isinstance(msg, str):
            continue
        if len(msgs[embed_count] + msg) > 3500:
            embed_count += 1
            msgs.append('')
        msgs[embed_count] += msg + "\n"
    return msgs


def duration_to_string(duration: int):
    seconds = duration % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    if hour > 0:
        return "%dh %02dm %02ds" % (hour, minutes, seconds)
    else:
        return "%02dm %02ds" % (minutes, seconds)
