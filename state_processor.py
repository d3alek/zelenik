import re

DEFAULT_WRITE = "high" 
DEFAULT_DELTA = 0
DEFAULT_DELETE = "no"
REQUIRED_ACTION_ATTRIBUTES = ['sense', 'gpio', 'threshold']

# action has the form sense|<pin#>|<H,L>|<thresh>|<delta>
ACTION_PATTERN = re.compile(r'^([a-zA-Z0-9-]+)\|(\d+)\|([HL])\|(\d+)\|(\d+)$')

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

def action(sense, gpio, write, threshold, delta):
    return {"sense": sense, "gpio": gpio, "write": write, "threshold": threshold, "delta": delta}

def explode_action(compact_action):
    m = ACTION_PATTERN.match(compact_action)
    if m is None:
        error("explode_action", "Could not explode action %s" % compact_action)
        return compact_action
    sense = m.group(1)
    gpio = int(m.group(2))
    write = explode_write(m.group(3))
    threshold = int(m.group(4))
    delta = int(m.group(5))

    if sense == 'time':
        threshold = seconds_to_timestamp(threshold)
        delta = seconds_to_timestamp(delta)

    return action(sense, gpio, write, threshold, delta)

def compact_action(exploded):
    if type(exploded) is not dict:
        error('compact_action', 'Could not compact action because it is not a dict: %s' % exploded)
        return exploded
    if not set(exploded.keys()).issuperset(REQUIRED_ACTION_ATTRIBUTES):
        error('compact_actions', 'Could not compact action because it does not have all the required attributes: %s' % exploded)
        return exploded

    threshold = exploded['threshold']
    delta = exploded.get('delta', DEFAULT_DELTA)
    if exploded['sense'] == 'time':
        threshold = timestamp_to_seconds(threshold)
        delta = timestamp_to_seconds(delta)

    write = compact_write(exploded.get('write', DEFAULT_WRITE))
    return '%s|%d|%s|%d|%d' % (exploded['sense'], exploded['gpio'], write, threshold, delta)

def explode_actions(actions):
    return list(map(explode_action, actions))

def compact_actions(actions):
    return list(map(compact_action, actions))

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
