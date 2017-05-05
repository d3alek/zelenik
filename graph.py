import matplotlib
matplotlib.use('svg')

from matplotlib import pyplot as plt
from matplotlib.dates import date2num, AutoDateLocator, AutoDateFormatter, DateFormatter

from db_driver import parse_isoformat, flat_map

from dateutil import tz

import matplotlib.gridspec as gridspec

timezone = tz.gettz('Europe/Sofia')

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

def handle_graph(db, a_thing, since_days=1):
    thing = db.resolve_thing(a_thing)
    history = db.load_history(thing, 'reported', since_days=since_days)
    displayables = db.load_state(thing, 'displayables')
    should_graph = flat_map(displayables, "graph")
    displayable_color = flat_map(displayables, "color")
    displayable_type = flat_map(displayables, "type")

    times = list(map(lambda s: parse_isoformat(s['timestamp_utc']), history))
    plot_times = list(map(lambda t: date2num(t), times))
    senses = list(map(lambda s: get_senses(s['state']), history))
    writes = list(map(lambda s: get_write(s['state']), history))

    f = plt.figure(figsize=(12, 6), dpi=100)

    gs = gridspec.GridSpec(2, 1, height_ratios=[7,1])

    degree_plot = plt.subplot(gs[0])
    writes_plot = plt.subplot(gs[1], sharex=degree_plot)
    percent_plot = degree_plot.twinx()
    percent_plot.axes.yaxis.tick_left()

    writes_plot.axes.xaxis.set_visible(False)
    
    locator = AutoDateLocator(tz=timezone)
    degree_plot.axes.yaxis.tick_right()
    degree_plot.axes.xaxis.set_major_locator(locator)
    degree_plot.axes.xaxis.set_major_formatter(AutoDateFormatter(locator, tz=timezone))
    writes_plot.axes.yaxis.tick_right()

    percent_plot.set_ylabel('%')
    percent_plot.axes.yaxis.set_label_position('left')

    degree_plot.set_ylabel('°C')
    degree_plot.axes.yaxis.set_label_position('right')

    if len(senses) > 0:
        sense_types = set()
        for sense_state in senses:
            sense_types = sense_types.union(sense_state.keys())

        sense_types = sorted(sense_types) 
        sense_types = list(filter(lambda s: should_graph.get(s, "yes") == "yes", sense_types))
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
        alias = ""
        values = []
        times = []
        wrong_times = []
        wrong_values = []
        for sense_state, time in zip(senses, plot_times):
            if sense_state.get(sense_type) is not None:
                previous_value = 0
                if len(values) > 0:
                    previous_value = values[-1]

                value = sense_state[sense_type]
                if type(value) is dict:
                    wrong, float_value = parse_sense(value['value'])
                    if not wrong:
                        values.append(float_value)
                        times.append(time)
                    else:
                        wrong_times.append(time)
                        wrong_values.append(previous_value)
                    if value.get('alias'):
                        alias = value['alias']
                else:
                    wrong, float_value = parse_sense(value)
                    if not wrong:
                        values.append(float_value)
                        times.append(time)
                    else:
                        wrong_times.append(time)
                        wrong_values.append(previous_value)

        if not alias or alias == "":
            label = sense_type
        else: 
            label = alias

        color = displayable_color.get(sense_type, 'black')
        if displayable_type.get(sense_type, 'number') == 'percent':
            p = percent_plot
        else:
            p = degree_plot

        p.plot(times, values, label=label, color=color)
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
        alias = ""
        values = []
        intervals = []
        interval = None
        times = []
        
        for writes_state, time in zip(writes, plot_times):
            if writes_state.get(writes_type) is not None:
                value = writes_state[writes_type]
                if type(value) is dict:
                    converted = float(value['value'])
                    alias = value['alias']
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

        if alias == "":
            label = writes_type
        else: 
            label = alias

        y = writes_start + writes_index*writes_offset

        writes_plot.broken_barh(intervals, (y+0.5, writes_offset+0.5)) # -0.5 to center on named y axis

        labels.append(label)
        yticks.append(y)

    writes_plot.set_yticks(yticks)
    writes_plot.set_yticklabels(labels)
        
    degree_plot.axes.autoscale()
    degree_plot.grid(True)

    # importantly here we should use the dealiased thing
    since_days_suffix = ''
    if since_days > 1:
        since_days_suffix = '-%d' % since_days
    image_location = 'db/%s/graph%s.png' % (thing, since_days_suffix)

    # legend to top of plot, based on example from http://matplotlib.org/users/legend_guide.html
    percent_plot.legend(bbox_to_anchor=(0., 1.02, 0.5, .102), loc=3,
                       ncol=2, mode="expand", borderaxespad=0.)
    degree_plot.legend(bbox_to_anchor=(0.5, 1.02, 0.5, .102), loc=3,
                       ncol=2, mode="expand", borderaxespad=0.)

    plt.savefig(image_location, dpi=100, bbox_inches='tight')

    with open(image_location, 'rb') as f:
        image_bytes = f.read()

    content_type = 'image/png'
    return content_type, image_bytes

