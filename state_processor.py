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

def seconds_to_timestamp(seconds):
    hours = seconds // (60*60)
    minutes = (seconds // 60) % 60
    return "%d:%02d" % (hours, minutes)

def timestamp_to_seconds(timestamp):
    if type(timestamp) is int:
        return timestamp

    hours, minutes = map(int, timestamp.split(':'))

    return hours * 3600 + minutes * 60

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

    if delete != "yes" and sense == 'time':
        threshold = seconds_to_timestamp(threshold)
        delta = seconds_to_timestamp(delta)

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

        delta = value.get('delta', DEFAULT_DELTA)
        threshold = value['threshold']

        if sense == 'time':
            delta = timestamp_to_seconds(delta)
            threshold = timestamp_to_seconds(threshold)

        if value.get('delete', DEFAULT_DELETE) == 'yes':
            delta_or_delete = DELETE
        else:
            delta_or_delete = delta

        compacted_value = '%d~%d' % (threshold, delta_or_delete)
        compacted[compacted_key] = compacted_value

    return compacted

def scale_capacitive_humidity(value):
    normalized = (value - 300) / (800 - 300)
    normalized = int(normalized * 100)
    if normalized < 0:
        normalized = 0
    elif normalized > 100:
        normalized = 100
    
    return normalized

def normalize_capacitive_humidity(value):
    if type(value) is dict and value.get('original'):
        info('normalize_capacitive_humidity', 'Capacitive humidity seems already normalized: %s' % value)
        return value

    elif type(value) is int:
        d = {}
        original = value
    elif type(value) is dict and value.get('value'):
        d = value
        original = value.get('value')
    else:
        error('normalize_capacitive_humidity', 'Expected capacitive humidity value to be either an integer or a dict with value element, got %s instead.' % value)
        return value

    scaled_value = scale_capacitive_humidity(original) 
    d['original'] = original
    d['value'] = scaled_value
    return d


def explode(json):
    exploded = {}
    for key, value in json.items():
        if key == 'actions':
            exploded_value = explode_actions(value)
        elif key == 'time' and type(value) is int:
            exploded_value = seconds_to_timestamp(value)
        elif key == 'I2C-32c':
            exploded_value = normalize_capacitive_humidity(value)
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
        elif key == 'time' and type(value) is str:
            compacted_value = timestamp_to_seconds(value)
        elif type(value) is dict:
            compacted_value = compact(value)
        else:
            compacted_value = value
        compacted[key] = compacted_value
    return compacted 
