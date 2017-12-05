import re
from numbers import Number
from datetime import datetime, timedelta

from logger import Logger
logger = Logger("state_processor")

DEFAULT_WRITE = "high" 
DEFAULT_DELTA = 0
DEFAULT_DELETE = "no"
REQUIRED_ACTION_ATTRIBUTES = ['sense', 'gpio', 'threshold']
TYPICAL_AWAKE_SECONDS = 30

# action has the form sense|<pin#>|<H,L>|<thresh>|<delta>
ACTION_PATTERN = re.compile(r'^([a-zA-Z0-9-]+)\|(\d+)\|([HL])\|(\d+)\|(\d+)$')

WRONG_VALUE_INT = -1003 # taken from EspIdiot, keep it in sync

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
        log = logger.of('compact_write')
        log.error("Word is neither high nor low - %s. Returning default %s" % (word, DEFAULT_WRITE))
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
    log = logger.of('explode_action')
    if isinstance(compact_action, dict):
        log.info('Action looks already exploded: %s' % compact_action)
        return compact_action
    m = ACTION_PATTERN.match(compact_action)
    if m is None:
        log.error("Could not explode action %s" % compact_action)
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
    log = logger.of('compact_action')
    if type(exploded) is not dict:
        log.error('Could not compact action because it is not a dict: %s' % exploded)
        return exploded
    if not set(exploded.keys()).issuperset(REQUIRED_ACTION_ATTRIBUTES):
        log.error('Could not compact action because it does not have all the required attributes: %s' % exploded)
        return exploded

    threshold = exploded['threshold']
    delta = exploded.get('delta', DEFAULT_DELTA)
    sense = exploded['sense']
    if sense == 'time':
        threshold = timestamp_to_seconds(threshold)
        delta = timestamp_to_seconds(delta)

    write = compact_write(exploded.get('write', DEFAULT_WRITE))

    return '%s|%d|%s|%d|%d' % (exploded['sense'], exploded['gpio'], write, threshold, delta)

def explode_actions(actions):
    return list(map(explode_action, actions))

def compact_actions(actions):
    return list(map(compact_action, actions))

def explode_deprecated_sense(value):
    log = logger.of("explode_deprecated_sense")
    if isinstance(value, Number):
        log.info("Deprecated sense value number: %s" % value)
        return {"value": value}

    else:
        try:
            return {"value": float(value)}
        except ValueError:
            pass

    if len(value) > 0 and value[0] == 'w':
        log.info("Deprecated sense value number marked as wrong with a 'w' character: %s" % value)
        return {"wrong": int(value[1:])}

    return None

def explode_sense(value):
    log = logger.of('explode_sense')
    alias = None
    if isinstance(value, dict):
        alias = value.get('alias', None)
        value = value.get('value', None)

    enriched_sense = explode_deprecated_sense(value)
    if not enriched_sense:
        split = value.split('|')
        if len(split) != 4:
            log.error("Expected value to be 4 parts split by |, got %s instead" % value)
            return None

        enriched_sense = {}
        if int(split[1]) != WRONG_VALUE_INT:
            enriched_sense['expected'] = int(split[1])
        if int(split[2]) != WRONG_VALUE_INT:
            enriched_sense['ssd'] = int(split[2])
        if split[3] == 'w':
            enriched_sense['wrong'] = float(split[0])
        else:
            enriched_sense['value'] = float(split[0])

    if alias:
        enriched_sense['alias'] = alias

    return enriched_sense

def explode_senses(senses):
    log = logger.of('explode_senses')
    exploded = {}
    for key, value in senses.items():
        if key == 'time' and isinstance(value, Number):
            exploded[key] = seconds_to_timestamp(value)
            continue

        enriched_sense = explode_sense(value)

        if enriched_sense is None:
            log.info('Not exploding sense %s:%s because of a parsing failure' % (key, value))
            exploded[key] = value
            continue

        exploded[key] = enriched_sense

    return exploded

def datetime_from_epoch(seconds):
    return datetime.utcfromtimestamp(seconds)

def almost_equal(a, b, max_delta):
    return abs(a - b) < max_delta

def explode(json, previous_json={}, previous_timestamp_string=None):
    exploded = {}
    log = logger.of('explode')
    for key, value in json.items():
        previous_value = previous_json.get(key, {})
        if key == 'b':
            key = 'boot_utc'
            boot_utc = datetime_from_epoch(int(value))

            previous_boot_utc_string = previous_json.get('boot_utc')

            if previous_boot_utc_string:
                previous_boot_utc = parse_isoformat(previous_boot_utc_string)

                sleep_seconds = json.get('config', {}).get('sleep', 0)
                abs_delta_seconds = abs((boot_utc - previous_boot_utc).total_seconds())

                if abs_delta_seconds < 3: # expected fluctuations due to clock inaccuracies
                    boot_utc = previous_boot_utc
                elif previous_timestamp_string:
                    update_delta_seconds = (datetime.utcnow() - parse_isoformat(previous_timestamp_string)).total_seconds()
                    print("Update delta seconds is", update_delta_seconds)
                    if almost_equal(update_delta_seconds, sleep_seconds, TYPICAL_AWAKE_SECONDS):
                        log.info('Looks like device has slept, adjusting boot for %d seconds ago' % abs_delta_seconds)
                        boot_utc = previous_boot_utc

            exploded_value = boot_utc.isoformat(sep=' ')

        elif key == 'actions':
            exploded_value = explode_actions(value)
        elif key == 'senses':
            exploded_value = explode_senses(value)
        elif type(value) is dict:
            exploded_value = explode(value, previous_value, previous_timestamp_string)
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
