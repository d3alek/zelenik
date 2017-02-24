import re

DELETE = -2
DEFAULT_WRITE = "high" 
DEFAULT_DELTA = 0
DEFAULT_DELETE = "no"

# key has the form A|sense|<pin#><H,L or absent>
ACTION_KEY_PATTERN = re.compile(r'^A\|([a-zA-Z0-9-]+)\|(\d+)([HL]?)$')

# value has the form <tresh>~<delta>
ACTION_VALUE_PATTERN = re.compile(r'^(\d+)~(-?\d+)$')

def error(method, message):
    print("! state_processor/%s: %s" % (method, message))

def explode_write(letter):
    if letter == 'H':
        return 'high'
    if letter == 'L':
        return 'low'

    # default
    return DEFAULT_WRITE

def compact_write(word):
    if word == 'high':
        return 'H'

    elif word == 'low':
        return 'L'

    else:
        error("compact_write", "Word is neither high nor low - %s. Returning default %s" % (word, DEFAULT_WRITE))
        return compact_write(DEFAULT_WRITE)

def parse_action(key, value):
    m = ACTION_KEY_PATTERN.match(key)
    if m is None:
        error("parse_action", "Could not parse action key %s" % key)
        return None, None
    sense = m.group(1)
    gpio = int(m.group(2))
    write = explode_write(m.group(3))

    m = ACTION_VALUE_PATTERN.match(value)
    if m is None:
        error("parse_action", "Could not parse action value %s" % value)
        return None, None

    threshold = int(m.group(1))
    delta = int(m.group(2))
    if delta == -2:
        delete = "yes"
    else:
        delete = "no"

    return sense, {"gpio": gpio, "write": write, "threshold": threshold, "delta": delta, "delete": delete}

def explode_actions(actions):
    exploded = {}
    for key, value in actions.items():

        sense, action = parse_action(key, value)
        if action is None:
            exploded[key] = value
        else:
            exploded[sense] = action

    return exploded

def compact_actions(actions):
    compacted = {}

    for key, value in actions.items():
        if type(value) is not dict:
            error('compact_actions', 'Could not compact action with non-dict value: %s' % actions)
            compacted[key] = value
            continue
        if value.get('gpio') is None or value.get('threshold') is None:
            error('compact_actions', 'Could not compact action incomplete dict value: %s' % actions)
            compacted[key] = value
            continue
        sense = key
        compacted_key = 'A|%s|%d%s' % (sense, value['gpio'], compact_write(value.get('write', DEFAULT_WRITE)))

        delta_or_delete = value.get('delta', DEFAULT_DELTA)
        if value.get('delete', DEFAULT_DELETE) == 'yes':
            delta_or_delete = DELETE

        compacted_value = '%d~%d' % (value['threshold'], delta_or_delete)
        compacted[compacted_key] = compacted_value

    return compacted

def explode(json):
    exploded = {}
    for key, value in json.items():
        if key == 'actions':
            exploded_value = explode_actions(value)
        elif type(value) is dict:
            exploded_value = explode(value)
        else:
            exploded_value = value
        exploded[key] = exploded_value 
    return exploded

def compact(json):
    compacted = {}

    for key, value in json.items():
        if key == 'actions':
            compacted_value = compact_actions(value)
        elif type(value) is dict:
            compacted_value = compact(value)
        else:
            compacted_value = value
        compacted[key] = compacted_value
    return compacted 
