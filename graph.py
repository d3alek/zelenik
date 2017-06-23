from logger import Logger
logger = Logger("graph")

import matplotlib
matplotlib.use('svg')

from matplotlib import pyplot as plt
from matplotlib.dates import date2num, AutoDateLocator, AutoDateFormatter, DateFormatter

from db_driver import parse_isoformat, flat_map

from dateutil import tz

import matplotlib.gridspec as gridspec

from scipy import signal

from enchanter import Enchanter

from operator import itemgetter

from datetime import datetime, timedelta

timezone = tz.gettz('Europe/Sofia')

DEFAULT_SINCE_DAYS = 1
DEFAULT_MEDIAN_KERNEL = 3
DEFAULT_WRONGS = False

def get_write(state):
    if state.get('write'):
        return state['write']
    elif state.get('mode'):
        return state['mode']
    else:
        return {}

def get_senses(state):
    if state.get('senses'):
        return state['senses']
    else:
        return {}

def parse_sense(maybe_wrong):
    if not maybe_wrong:
        return (True, 0)
    wrong = False
    value = 0
    if type(maybe_wrong) is str and maybe_wrong.startswith('w'):
        wrong = True
    else:
        try:
            value = float(maybe_wrong)
        except ValueError:
            wrong = True

    return (wrong, value)

def graph_types(displayable_type, should_graph):
    number_found = False
    percent_found = False
    for key, value in displayable_type.items():
        if should_graph.get(key, 'no') == 'no':
            continue
        if value == 'number' or value == 'temp':
            number_found = True
        elif value == 'percent':
            percent_found = True

    return number_found, percent_found

def parse_formdata(formdata):
    since_days = DEFAULT_SINCE_DAYS
    median_kernel = DEFAULT_MEDIAN_KERNEL
    wrongs = DEFAULT_WRONGS
    graphable = None
    if 'since' in formdata:
        since_days = int(formdata['since'].value)
    if 'median' in formdata:
        median_kernel = int(formdata['median'].value)
    if 'wrongs' in formdata:
        wrongs = formdata['wrongs'].value == 'True'
    if 'graphable' in formdata:
        graphable = {}
        graphable_list = formdata['graphable']
        if not isinstance(graphable_list, list):
            graphable_list = [graphable_list]
        for graphable_text in graphable_list:
            split = graphable_text.value.split('/')
            sense = split[0]
            subsense = split[1]
            graphable.setdefault(sense, []).append(subsense)

    return since_days, median_kernel, wrongs, graphable

def fast_enchant(reported):
    global thing, displayables, enchanter, enchanter_config, old_enchanted

    old_enchanted = enchanter.enchant(thing, reported = reported, config = enchanter_config, displayables = displayables, alias=False, old_enchanted = old_enchanted)

    return old_enchanted

# assumes history is sorted in ascending order
def subsample_history(history, conditions):
    log = logger.of('subsample_history')
    sorted_conditions = sorted(conditions, key=itemgetter(0))
    subsampled = []
    index = 0
    for earlier_than, subsample_rate in sorted_conditions:
        next_index = len(history[index:])
        for increment_index, state in enumerate(history[index:]):
            if parse_isoformat(state['timestamp_utc']) > earlier_than:
                next_index = index + increment_index
                break

        subsampled.extend(history[index:next_index:subsample_rate])
        index = next_index

    log.info('Subsampling reduced data from %d to %d' % (len(history), len(subsampled)))

    return subsampled

def handle_graph(db, a_thing, since_days=DEFAULT_SINCE_DAYS, median_kernel=DEFAULT_MEDIAN_KERNEL, wrongs=DEFAULT_WRONGS, graphable=None, formdata=None):
    global thing, displayables, enchanter, enchanter_config, old_enchanted

    log = logger.of('handle_graph')
    if formdata:
        since_days, median_kernel, wrongs, graphable = parse_formdata(formdata)
    else:
        graphable = {}

    thing = db.resolve_thing(a_thing)
    history = db.load_history(thing, 'reported', since_days=since_days)

    ten_minutes_ago = datetime.utcnow() - timedelta(minutes=10) # so every 5 minutes
    sparse_history = subsample_history(history, [(ten_minutes_ago, 10)])
    
    displayables = db.load_state(thing, 'displayables')

    enchanter = Enchanter()
    enchanter_config = db.load_state(thing, 'enchanter')
    old_enchanted = {}

    enchanted_history = list(map(fast_enchant, sparse_history))

    should_graph = flat_map(displayables, "graph")
    displayable_color = flat_map(displayables, "color")
    displayable_type = flat_map(displayables, "type")
    displayable_alias = flat_map(displayables, "alias")

    times = list(map(lambda s: parse_isoformat(s['timestamp_utc']), enchanted_history))
    plot_times = list(map(lambda t: date2num(t), times))
    senses = list(map(lambda s: get_senses(s['state']), enchanted_history))
    writes = list(map(lambda s: get_write(s['state']), enchanted_history))


    f = plt.figure(figsize=(12, 6), dpi=100)

    gs = gridspec.GridSpec(2, 1, height_ratios=[7,1])

    sense_plot = plt.subplot(gs[0])
    writes_plot = plt.subplot(gs[1], sharex=sense_plot)

    writes_plot.axes.xaxis.set_visible(False)
    
    locator = AutoDateLocator(tz=timezone)
    sense_plot.axes.xaxis.set_major_locator(locator)
    sense_plot.axes.xaxis.set_major_formatter(AutoDateFormatter(locator, tz=timezone))
    writes_plot.axes.yaxis.tick_right()

    numbers, percents = graph_types(displayable_type, should_graph)

    if numbers and percents: 
        sense_twin_plot = sense_plot.twinx()
        sense_twin_plot.axes.yaxis.tick_left()
        sense_plot.axes.yaxis.tick_right()
        sense_plot.set_ylabel('°C')
        sense_plot.axes.yaxis.set_label_position('right')
        sense_twin_plot.set_ylabel('%')
        sense_twin_plot.axes.yaxis.set_label_position('left')
    elif numbers:
        sense_twin_plot = None
        sense_plot.set_ylabel('°C')
        sense_plot.axes.yaxis.set_label_position('right')
    elif percents:
        sense_twin_plot = None
        sense_plot.set_ylabel('%')
        sense_plot.axes.yaxis.tick_left()
        sense_plot.axes.yaxis.set_label_position('left')

    if len(senses) > 0:
        if graphable:
            sense_types = graphable.keys() 
        else:
            sense_types = set()
            for sense_state in senses:
                sense_types = sense_types.union(sense_state.keys())

            sense_types = sorted(sense_types) 
            sense_types = list(filter(lambda s: should_graph.get(s, "no") == "yes", sense_types))
            if 'time' in sense_types:
                sense_types.remove('time')
    else:
        sense_types = []

    if len(sense_types) == 0:
        content_type = 'image/png'
        with open('view/no-data.png', 'rb') as f:
            bytes = f.read()
        return content_type, bytes

    for sense_type in sense_types:
        values = []
        times = []
        wrong_times = []
        wrong_values = []
        subtypes = graphable.get(sense_type, ['valueOrNormalized'])
        for subtype in subtypes:
            for sense_state, time in zip(senses, plot_times):
                if sense_state.get(sense_type) is not None:
                    previous_value = 0
                    if len(values) > 0:
                        previous_value = values[-1]

                    value = sense_state[sense_type]
                    if type(value) is dict:
                        if subtype == 'valueOrNormalized':
                            # check if 'normalized' exists, use it instead of value
                            sense = value.get("normalized", None)
                            if not sense:
                                sense = value.get("value", None)
                        else:
                            sense = value.get(subtype)

                        wrong, float_value = parse_sense(sense)
                        if not wrong:
                            values.append(float_value)
                            times.append(time)
                        else:
                            wrong_times.append(time)
                            wrong_values.append(previous_value)
                    elif subtype in ["value", "valueOrNormalized"]:
                        wrong, float_value = parse_sense(value)
                        if not wrong:
                            values.append(float_value)
                            times.append(time)
                        else:
                            wrong_times.append(time)
                            wrong_values.append(previous_value)

        label = displayable_alias.get(sense_type)
        if not label:
            label = sense_type

        color = displayable_color.get(sense_type, 'black')

        if sense_twin_plot and displayable_type.get(sense_type, 'number') == 'percent':
            p = sense_twin_plot
        else:
            p = sense_plot

        filtered_values = signal.medfilt(values, median_kernel)
        p.plot(times, filtered_values, label=label, color=color)
        if wrongs:
            p.plot(wrong_times, wrong_values, 'rx')

    if len(writes) > 0:
        writes_types = sorted(writes[-1].keys()) 
    else:
        writes_types = []

    writes_start = 0 
    writes_offset = -2
    labels = []
    yticks = []
    for writes_index, writes_type in enumerate(writes_types):
        values = []
        intervals = []
        interval = None
        times = []
        
        for writes_state, time in zip(writes, plot_times):
            if writes_state.get(writes_type) is not None:
                value = writes_state[writes_type]
                if type(value) is dict:
                    converted = float(value['value'])
                else:
                    converted = int(value)

                if converted == 1:
                    if not interval:
                        interval = (time, 0.0001) # about 1 minute
                    else:
                        interval = (interval[0], time-interval[0])
                else:
                    if interval:
                        interval = (interval[0], time-interval[0])
                        intervals.append(interval)
                        interval = None

        if interval:
            intervals.append(interval)

        label = displayable_alias.get(writes_type)
        if not label:
            label = writes_type

        y = writes_start + writes_index*writes_offset

        writes_plot.broken_barh(intervals, (y+0.5, writes_offset+0.5)) # -0.5 to center on named y axis

        labels.append(label)
        yticks.append(y)

    writes_plot.set_yticks(yticks)
    writes_plot.set_yticklabels(labels)
        
    sense_plot.axes.autoscale()
    sense_plot.grid(True)

    # importantly here we should use the dealiased thing
    if formdata:
        image_location = "db/%s/temp.png" % thing

    else:
        image_location = 'db/%s/graph-%d-median-%d' % (thing, since_days, median_kernel)
        if wrongs:
            image_location += '-w'

        image_location += '.png'

    # legend to top of plot, based on example from http://matplotlib.org/users/legend_guide.html
    if sense_twin_plot:
        sense_twin_plot.legend(bbox_to_anchor=(0., 1.02, 0.5, .102), loc=3, ncol=2, mode="expand", borderaxespad=0.)
        sense_plot.legend(bbox_to_anchor=(0.5, 1.02, 0.5, .102), loc=3, ncol=2, mode="expand", borderaxespad=0.)
    else:
        sense_plot.legend(bbox_to_anchor=(0., 1.02, 1., .102), loc=3, ncol=3, mode="expand", borderaxespad=0.)

    plt.savefig(image_location, dpi=100, bbox_inches='tight')

    with open(image_location, 'rb') as f:
        image_bytes = f.read()

    content_type = 'image/png'
    return content_type, image_bytes

