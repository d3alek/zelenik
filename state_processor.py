import re
from numbers import Number

DEFAULT_WRITE = "high" 
DEFAULT_DELTA = 0
DEFAULT_DELETE = "no"
REQUIRED_ACTION_ATTRIBUTES = ['sense', 'gpio', 'threshold']
RESISTIVE_MOISTURE_SENSES = ['I2C-8', 'I2C-9', 'I2C-10']

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
    if isinstance(timestamp, Number):
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

    elif sense in RESISTIVE_MOISTURE_SENSES:
        threshold = resistive_humidity_to_percent(threshold)
        delta = resistive_humidity_to_percent(delta)

    elif sense == "I2C-32c":
        threshold = scale_capactive_humidity(threshold)
        delta = capacitive_humidity_to_percent(delta)

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
    sense = exploded['sense']
    if sense == 'time':
        threshold = timestamp_to_seconds(threshold)
        delta = timestamp_to_seconds(delta)
    elif sense in RESISTIVE_MOISTURE_SENSES:
        threshold = resistive_humidity_to_analog(threshold)
        delta = resistive_humidity_to_analog(delta)
    elif sense == "I2C-32c":
        threshold = capacitive_humidity_to_analog(threshold)
        delta = capacitive_humidity_to_analog(delta)

    write = compact_write(exploded.get('write', DEFAULT_WRITE))
    return '%s|%d|%s|%d|%d' % (exploded['sense'], exploded['gpio'], write, threshold, delta)

def explode_actions(actions):
    return list(map(explode_action, actions))

def compact_actions(actions):
    return list(map(compact_action, actions))

def capacitive_humidity_to_percent(value):
    return scale_to_percent(value, 300, 800)

def resistive_humidity_to_percent(value):
    return scale_to_percent(value, 0, 800)

def capacitive_humidity_to_analog(value):
    return scale_to_analog(value, 300, 800)

def resistive_humidity_to_analog(value):
    return scale_to_analog(value, 0, 800)

def scale_to_percent(value, low, high):
    normalized = (value - low) / (high - low)
    normalized = normalized * 100
    if normalized < 0:
        normalized = 0
    elif normalized > 100:
        normalized = 100
    
    return normalized

def scale_to_analog(value, low, high):
    normalized = value / 100
    normalized = int(normalized * (high - low) + low)

    if normalized < 0:
        normalized = 0
    elif normalized > 1024:
        normalized = 1024
    
    return normalized

def extract_value(value_json):
    if isinstance(value_json, Number):
        return value_json, False
    elif isinstance(value_json, str) and value_json.startswith('w'):
        return value_json, True
    elif type(value_json) is dict:
        value = value_json.get('original')
        wrong = 'wrong' in value_json.keys()
        if isinstance(value, Number):
            return value, wrong

        value = value_json.get('value')
        if isinstance(value, Number):
            return value, wrong
        elif isinstance(value, str) and value.startswith('w'):
            return value, True
    error('extract_value', 'Expected value to be either a number or a dict with value number or marked as wrong, got %s instead.' % value_json)
    return "unexpected", True

def normalize(value, scale_function):
    return scale_function(value) 

def explode(json, previous_json={}):
    exploded = {}
    previous_timestamp = previous_json.get('timestamp_utc', None)
    for key, value in json.items():
        previous_value = previous_json.get(key, {})
        if key == 'actions':
            exploded_value = explode_actions(value)
        elif key == 'time' and isinstance(value, Number):
            exploded_value = seconds_to_timestamp(value)
        elif key == 'I2C-32c' or key in RESISTIVE_MOISTURE_SENSES:
            if key == 'I2C-32c':
                transform = capacitive_humidity_to_percent
            else:
                transform = resistive_humidity_to_percent

            exploded_value = {}
            to_normalize = None
            if isinstance(value, dict):
                exploded_value = dict(value)
                exploded_value.pop('value', None)

            extracted_number, wrong = extract_value(value)

            if wrong:
                exploded_value['wrong'] = extracted_number
                if previous_value:
                    prev_extracted_number, prev_wrong = extract_value(previous_value)
                    if isinstance(prev_extracted_number, Number):
                        to_normalize = prev_extracted_number
                        if prev_wrong:
                            exploded_value['from'] = previous_value.get('from', None)
                        else:
                            exploded_value['from'] = previous_timestamp 
            else:
                to_normalize = extracted_number

            if to_normalize:
                exploded_value['original'] = to_normalize 
                normalized = normalize(to_normalize, transform)
                exploded_value['value'] = normalized
        elif type(value) is dict:
            exploded_value = explode(value, previous_value)
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
