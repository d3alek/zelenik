import re
from numbers import Number
from datetime import datetime, timedelta

DEFAULT_WRITE = "high" 
DEFAULT_DELTA = 0
DEFAULT_DELETE = "no"
REQUIRED_ACTION_ATTRIBUTES = ['sense', 'gpio', 'threshold']
RESISTIVE_MOISTURE_SENSES = ['I2C-8', 'I2C-9', 'I2C-10']

# action has the form sense|<pin#>|<H,L>|<thresh>|<delta>
ACTION_PATTERN = re.compile(r'^([a-zA-Z0-9-]+)\|(\d+)\|([HL])\|(\d+)\|(\d+)$')

WRONG_VALUE_INT = -1003 # taken from EspIdiot, keep it in sync

def error(method, message):
    print("! state_processor/%s: %s" % (method, message))

def info(method, message):
    print("  state_processor/%s: %s" % (method, message))

# parse iso format datetime with sep=' '
def parse_isoformat(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S.%f")
    except ValueError:
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")

def less_than_a_day_ago(time):
    return time and datetime.utcnow() - timedelta(days=1) < parse_isoformat(time)

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

def normalize(value, scale_function):
    return scale_function(value) 

def explode_deprecated_sense(value):
    if isinstance(value, Number):
        info("explode_deprecated_sense", "Deprecated sense value integer: %s" % value)
        return {"value": value}

    if len(value) > 0 and value[0] == 'w':
        info("explode_deprecated_sense", "Deprecated sense value integer marked as wrong with a 'w' character: %s" % value)
        return {"wrong": int(value[1:])}

    return None

def explode_sense(value):
    alias = None
    if isinstance(value, dict):
        alias = value.get('alias', None)
        value = value.get('value', None)

    enriched_sense = explode_deprecated_sense(value)
    if not enriched_sense:
        split = value.split('|')
        if len(split) != 4:
            error("explode_sense", "Expected value to be 4 parts split by |, got %s instead" % value)
            return None

        enriched_sense = {}
        if int(split[1]) != WRONG_VALUE_INT:
            enriched_sense['expected'] = int(split[1])
        if int(split[2]) != WRONG_VALUE_INT:
            enriched_sense['ssd'] = int(split[2])
        if split[3] == 'w':
            enriched_sense['wrong'] = int(split[0])
        else:
            enriched_sense['value'] = int(split[0])

    if alias:
        enriched_sense['alias'] = alias

    return enriched_sense

def explode_senses(senses, previous_senses, previous_timestamp):
    exploded = {}
    for key, value in senses.items():
        previous_value = previous_senses.pop(key, {})
        if key == 'time' and isinstance(value, Number):
            exploded_value = seconds_to_timestamp(value)
            continue

        enriched_sense = explode_sense(value)
        previous_enriched_sense = previous_value

        if enriched_sense is None:
            info('explode_sense', 'Not exploding sense %s:%s because of a parsing failure' % (key, value))
            exploded[key] = value
            continue

        if 'value' not in enriched_sense.keys() and 'expected' not in enriched_sense.keys():
            # Pick value or expected from previous, idea is to always have an estimate of what a sensor shows and idea of how recent that showing is (leave it a UI responsibility)
            if previous_enriched_sense:
                if 'value' in previous_enriched_sense.keys():
                    enriched_sense['value'] = previous_enriched_sense['value']
                    enriched_sense['from'] = previous_timestamp
                elif 'expected' in previous_enriched_sense.keys():
                    enriched_sense['expected'] = previous_enriched_sense['expected']
                    enriched_sense['from'] = previous_timestamp
                if 'from' in previous_enriched_sense.keys():
                    enriched_sense['from'] = previous_enriched_sense['from']

        if key == 'I2C-32c' or key in RESISTIVE_MOISTURE_SENSES:
            if key == 'I2C-32c':
                transform = capacitive_humidity_to_percent
            else:
                transform = resistive_humidity_to_percent

            to_normalize = None
            to_normalize = enriched_sense.get('value', None)
            if to_normalize is None:
                to_normalize = enriched_sense.get('expected', None)
            if to_normalize is not None:
                normalized = normalize(to_normalize, transform)
                enriched_sense['normalized'] = normalized

        exploded[key] = enriched_sense

    if previous_senses and less_than_a_day_ago(previous_timestamp):
        # some senses remain from the past, take them if they are up to a day old
        for key, value in previous_senses.items():
            if isinstance(value, dict):
                timestamp = value.get('from', previous_timestamp)
                if less_than_a_day_ago(timestamp):
                    value['from'] = previous = timestamp
                    exploded[key] = value
                else:
                    info("explode_senses", "Forgetting previous sense %s because more than a day old: %s" % (key, timestamp))
    else:
        info("explode_senses", "Forgetting previous senses because more than a day old: %s" % previous_timestamp)

    return exploded

def explode(json, previous_json={}, previous_timestamp=None):
    exploded = {}
    for key, value in json.items():
        previous_value = previous_json.get(key, {})
        if key == 'actions':
            exploded_value = explode_actions(value)
        elif key == 'senses':
            exploded_value = explode_senses(value, previous_value, previous_timestamp)
        elif type(value) is dict:
            exploded_value = explode(value, previous_value, previous_timestamp)
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
